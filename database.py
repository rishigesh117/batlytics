"""
Batlytics — SQLite Database Layer
Handles all match data persistence for offline storage.
"""
import sqlite3
import os
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batlytics.db")


def get_connection(db_path=None):
    """Get a database connection."""
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None):
    """Initialize database tables."""
    conn = get_connection(db_path)
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_a TEXT NOT NULL,
            team_b TEXT NOT NULL,
            overs INTEGER NOT NULL,
            players_per_team INTEGER NOT NULL,
            toss_winner TEXT,
            toss_choice TEXT,
            status TEXT NOT NULL DEFAULT 'setup',
            winner TEXT,
            win_margin TEXT,
            potm_id INTEGER,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            team TEXT NOT NULL,
            name TEXT NOT NULL,
            batting_order INTEGER,
            FOREIGN KEY (match_id) REFERENCES matches(id)
        );

        CREATE TABLE IF NOT EXISTS innings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            batting_team TEXT NOT NULL,
            bowling_team TEXT NOT NULL,
            innings_number INTEGER NOT NULL,
            total_runs INTEGER NOT NULL DEFAULT 0,
            total_wickets INTEGER NOT NULL DEFAULT 0,
            total_overs_balls INTEGER NOT NULL DEFAULT 0,
            is_complete INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (match_id) REFERENCES matches(id)
        );

        CREATE TABLE IF NOT EXISTS balls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            innings_id INTEGER NOT NULL,
            over_number INTEGER NOT NULL,
            ball_number INTEGER NOT NULL,
            batsman_id INTEGER NOT NULL,
            bowler_id INTEGER NOT NULL,
            runs INTEGER NOT NULL DEFAULT 0,
            extras INTEGER NOT NULL DEFAULT 0,
            is_wide INTEGER NOT NULL DEFAULT 0,
            is_noball INTEGER NOT NULL DEFAULT 0,
            is_wicket INTEGER NOT NULL DEFAULT 0,
            is_bye INTEGER NOT NULL DEFAULT 0,
            is_legbye INTEGER NOT NULL DEFAULT 0,
            wicket_type TEXT,
            out_batsman_id INTEGER,
            fielder_id INTEGER,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (innings_id) REFERENCES innings(id),
            FOREIGN KEY (batsman_id) REFERENCES players(id),
            FOREIGN KEY (bowler_id) REFERENCES players(id)
        );

        CREATE TABLE IF NOT EXISTS commentary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            innings_id INTEGER NOT NULL,
            ball_id INTEGER NOT NULL,
            over_number INTEGER NOT NULL,
            ball_number INTEGER NOT NULL,
            commentary_text TEXT NOT NULL,
            is_boundary INTEGER NOT NULL DEFAULT 0,
            is_wicket INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (innings_id) REFERENCES innings(id),
            FOREIGN KEY (ball_id) REFERENCES balls(id)
        );

        CREATE TABLE IF NOT EXISTS partnerships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            innings_id INTEGER NOT NULL,
            batsman1_id INTEGER NOT NULL,
            batsman2_id INTEGER NOT NULL,
            runs INTEGER NOT NULL DEFAULT 0,
            balls INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (innings_id) REFERENCES innings(id),
            FOREIGN KEY (batsman1_id) REFERENCES players(id),
            FOREIGN KEY (batsman2_id) REFERENCES players(id)
        );
    """)

    conn.commit()

    # Add columns if they don't exist
    try:
        c.execute("ALTER TABLE balls ADD COLUMN is_legbye INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
        
    try:
        c.execute("ALTER TABLE balls ADD COLUMN fielder_id INTEGER")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()

    # Apply migrations for new columns
    try:
        c.execute("ALTER TABLE matches ADD COLUMN bowler_limit INTEGER DEFAULT 4")
        c.execute("ALTER TABLE matches ADD COLUMN team_a_captain TEXT")
        c.execute("ALTER TABLE matches ADD COLUMN team_b_captain TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Add fielder_id column for catches
    try:
        c.execute("ALTER TABLE balls ADD COLUMN fielder_id INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Add next_striker_id and next_non_striker_id for robust undo
    try:
        c.execute("ALTER TABLE balls ADD COLUMN next_striker_id INTEGER")
        c.execute("ALTER TABLE balls ADD COLUMN next_non_striker_id INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    conn.close()


# ─── Match CRUD ──────────────────────────────────────────────

def create_match(team_a, team_b, overs, players_per_team, bowler_limit=4, team_a_cap="", team_b_cap="", db_path=None):
    """Create a new match and return its ID."""
    conn = get_connection(db_path)
    c = conn.cursor()
    c.execute(
        "INSERT INTO matches (team_a, team_b, overs, players_per_team, bowler_limit, team_a_captain, team_b_captain, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'setup', ?)",
        (team_a, team_b, overs, players_per_team, bowler_limit, team_a_cap, team_b_cap, datetime.now().isoformat())
    )
    match_id = c.lastrowid
    conn.commit()
    conn.close()
    return match_id


def get_match(match_id, db_path=None):
    """Get match by ID."""
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_matches(db_path=None):
    """List all matches ordered by most recent."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM matches ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_match(match_id, **kwargs):
    """Update match fields."""
    conn = get_connection(kwargs.pop("db_path", None))
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [match_id]
    conn.execute(f"UPDATE matches SET {sets} WHERE id = ?", vals)
    conn.commit()
    conn.close()


# ─── Players ─────────────────────────────────────────────────

def add_player(match_id, team, name, batting_order=None, db_path=None):
    """Add a player to a match team."""
    conn = get_connection(db_path)
    c = conn.cursor()
    c.execute(
        "INSERT INTO players (match_id, team, name, batting_order) VALUES (?, ?, ?, ?)",
        (match_id, team, name, batting_order)
    )
    player_id = c.lastrowid
    conn.commit()
    conn.close()
    return player_id


def get_players(match_id, team=None, db_path=None):
    """Get players for a match, optionally filtered by team."""
    conn = get_connection(db_path)
    if team:
        rows = conn.execute(
            "SELECT * FROM players WHERE match_id = ? AND team = ? ORDER BY batting_order",
            (match_id, team)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM players WHERE match_id = ? ORDER BY team, batting_order",
            (match_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_player(player_id, db_path=None):
    """Get a single player by ID."""
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_player_names(db_path=None):
    """Get unique player names from the most recent match, excluding defaults."""
    conn = get_connection(db_path)
    
    # Get the ID of the most recent match
    match_row = conn.execute("SELECT id FROM matches ORDER BY id DESC LIMIT 1").fetchone()
    if not match_row:
        conn.close()
        return []
        
    match_id = match_row['id']
    
    # Get all real players from that match
    rows = conn.execute(
        "SELECT DISTINCT name FROM players WHERE match_id = ? AND name NOT LIKE 'Player %'",
        (match_id,)
    ).fetchall()
    
    conn.close()
    return [r['name'] for r in rows]


def get_team_last_lineup(team_name, db_path=None):
    """Get the player names and batting order for a team's last match."""
    conn = get_connection(db_path)
    
    # Find the most recent match where this team played
    match_row = conn.execute(
        "SELECT id FROM matches WHERE team_a = ? OR team_b = ? ORDER BY id DESC LIMIT 1", 
        (team_name, team_name)
    ).fetchone()
    
    if not match_row:
        conn.close()
        return []
        
    match_id = match_row['id']
    
    # Get the players for this team in that match
    players = conn.execute(
        "SELECT name FROM players WHERE match_id = ? AND team = ? ORDER BY batting_order",
        (match_id, team_name)
    ).fetchall()
    
    conn.close()
    return [r['name'] for r in players]


# ─── Innings ─────────────────────────────────────────────────

def create_innings(match_id, batting_team, bowling_team, innings_number, db_path=None):
    """Create innings and return its ID."""
    conn = get_connection(db_path)
    c = conn.cursor()
    c.execute(
        "INSERT INTO innings (match_id, batting_team, bowling_team, innings_number) "
        "VALUES (?, ?, ?, ?)",
        (match_id, batting_team, bowling_team, innings_number)
    )
    innings_id = c.lastrowid
    conn.commit()
    conn.close()
    return innings_id


def get_innings(match_id, innings_number=None, db_path=None):
    """Get innings for a match."""
    conn = get_connection(db_path)
    if innings_number:
        row = conn.execute(
            "SELECT * FROM innings WHERE match_id = ? AND innings_number = ?",
            (match_id, innings_number)
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    else:
        rows = conn.execute(
            "SELECT * FROM innings WHERE match_id = ? ORDER BY innings_number",
            (match_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


def update_innings(innings_id, db_path=None, **kwargs):
    """Update innings fields."""
    conn = get_connection(db_path)
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [innings_id]
    conn.execute(f"UPDATE innings SET {sets} WHERE id = ?", vals)
    conn.commit()
    conn.close()


# ─── Balls ───────────────────────────────────────────────────

def record_ball(innings_id, over_number, ball_number, batsman_id, bowler_id,
                runs=0, extras=0, is_wide=0, is_noball=0, is_wicket=0,
                is_bye=0, wicket_type=None, out_batsman_id=None, fielder_id=None, db_path=None):
    """Record a single ball delivery."""
    conn = get_connection(db_path)
    c = conn.cursor()
    c.execute(
        "INSERT INTO balls (innings_id, over_number, ball_number, batsman_id, "
        "bowler_id, runs, extras, is_wide, is_noball, is_wicket, is_bye, "
        "wicket_type, out_batsman_id, fielder_id, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (innings_id, over_number, ball_number, batsman_id, bowler_id,
         runs, extras, is_wide, is_noball, is_wicket, is_bye,
         wicket_type, out_batsman_id, fielder_id, datetime.now().isoformat())
    )
    ball_id = c.lastrowid
    conn.commit()
    conn.close()
    return ball_id

def update_ball_next_state(ball_id, next_striker_id, next_non_striker_id, db_path=None):
    """Save the striker and non_striker state immediately AFTER this ball was processed."""
    conn = get_connection(db_path)
    conn.execute(
        "UPDATE balls SET next_striker_id = ?, next_non_striker_id = ? WHERE id = ?",
        (next_striker_id, next_non_striker_id, ball_id)
    )
    conn.commit()
    conn.close()

def get_balls(innings_id, db_path=None):
    """Get all balls for an innings ordered by delivery."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM balls WHERE innings_id = ? ORDER BY over_number, ball_number",
        (innings_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_last_ball(innings_id, db_path=None):
    """Get the most recent ball in an innings."""
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM balls WHERE innings_id = ? ORDER BY id DESC LIMIT 1",
        (innings_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_ball(ball_id, db_path=None):
    """Delete a ball (for undo)."""
    conn = get_connection(db_path)
    conn.execute("DELETE FROM balls WHERE id = ?", (ball_id,))
    conn.commit()
    conn.close()


# ─── Statistics ──────────────────────────────────────────────

def get_batting_stats(innings_id, db_path=None):
    """Get batting statistics for all batsmen in an innings."""
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT
            p.id, p.name,
            COALESCE(SUM(CASE WHEN b.is_wide = 0 AND b.is_noball = 0 THEN b.runs
                              WHEN b.is_noball = 1 THEN b.runs
                              ELSE 0 END), 0) as runs,
            COUNT(CASE WHEN b.is_wide = 0 THEN b.id END) as balls_faced,
            COUNT(CASE WHEN b.runs = 4 AND b.is_wide = 0 THEN 1 END) as fours,
            COUNT(CASE WHEN b.runs = 6 AND b.is_wide = 0 THEN 1 END) as sixes,
            MAX(CASE WHEN b.is_wicket = 1 AND b.out_batsman_id = p.id THEN 1 ELSE 0 END) as is_out,
            MAX(CASE WHEN b.is_wicket = 1 AND b.out_batsman_id = p.id THEN b.wicket_type ELSE '' END) as how_out
        FROM players p
        LEFT JOIN balls b ON b.batsman_id = p.id AND b.innings_id = ?
        WHERE p.id IN (SELECT DISTINCT batsman_id FROM balls WHERE innings_id = ?)
        GROUP BY p.id
        ORDER BY MIN(b.id)
    """, (innings_id, innings_id)).fetchall()

    stats = []
    for r in rows:
        d = dict(r)
        balls = d["balls_faced"]
        d["strike_rate"] = round((d["runs"] / balls) * 100, 1) if balls > 0 else 0.0

        # Get dismissal details (bowler name, fielder name)
        d["bowler_name"] = ""
        d["fielder_name"] = ""
        if d["is_out"]:
            wk_row = conn.execute("""
                SELECT b.id, b.wicket_type, bp.name as bowler_name,
                       fp.name as fielder_name
                FROM balls b
                LEFT JOIN players bp ON bp.id = b.bowler_id
                LEFT JOIN players fp ON fp.id = b.fielder_id
                WHERE b.innings_id = ? AND b.is_wicket = 1
                  AND b.out_batsman_id = ?
                ORDER BY b.id DESC
                LIMIT 1
            """, (innings_id, d["id"])).fetchone()
            if wk_row:
                wk = dict(wk_row)
                if wk["wicket_type"] == "retired hurt":
                    # Check if they faced any balls after their retire hurt ball
                    returned = conn.execute("""
                        SELECT 1 FROM balls 
                        WHERE innings_id = ? AND batsman_id = ? AND id > ?
                        LIMIT 1
                    """, (innings_id, d["id"], wk["id"])).fetchone()
                    if returned:
                        d["is_out"] = 0
                        d["how_out"] = ""
                    else:
                        d["how_out"] = "retired hurt"
                else:
                    d["how_out"] = wk["wicket_type"]
                    d["bowler_name"] = wk.get("bowler_name", "") or ""
                    d["fielder_name"] = wk.get("fielder_name", "") or ""
        stats.append(d)

    conn.close()
    return stats


def get_bowling_stats(innings_id, db_path=None):
    """Get bowling statistics for all bowlers in an innings."""
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT
            p.id, p.name,
            COUNT(CASE WHEN b.is_wide = 0 AND b.is_noball = 0 THEN b.id END) as legal_balls,
            COALESCE(SUM(b.runs + (CASE WHEN b.is_wide=1 OR b.is_noball=1 THEN b.extras ELSE 0 END)), 0) as runs_conceded,
            COUNT(CASE WHEN b.is_wicket = 1 AND b.wicket_type NOT IN ('run out', 'retired hurt', 'retired out') THEN 1 END) as wickets,
            SUM(b.is_wide) as wides,
            SUM(b.is_noball) as noballs
        FROM players p
        JOIN balls b ON b.bowler_id = p.id AND b.innings_id = ?
        WHERE p.id IN (SELECT DISTINCT bowler_id FROM balls WHERE innings_id = ?)
        GROUP BY p.id
        ORDER BY MIN(b.id)
    """, (innings_id, innings_id)).fetchall()

    maidens_rows = conn.execute("""
        SELECT bowler_id, COUNT(*) as maidens
        FROM (
            SELECT bowler_id, over_number,
                   SUM(runs + CASE WHEN is_wide=1 OR is_noball=1 THEN extras ELSE 0 END) as over_runs,
                   COUNT(CASE WHEN is_wide = 0 AND is_noball = 0 THEN id END) as legal_balls
            FROM balls
            WHERE innings_id = ?
            GROUP BY bowler_id, over_number
        )
        WHERE over_runs = 0 AND legal_balls = 6
        GROUP BY bowler_id
    """, (innings_id,)).fetchall()
    conn.close()

    maidens_map = {r['bowler_id']: r['maidens'] for r in maidens_rows}

    stats = []
    for r in rows:
        d = dict(r)
        legal = d["legal_balls"]
        d["overs"] = f"{legal // 6}.{legal % 6}"
        d["economy"] = round((d["runs_conceded"] / (legal / 6)), 1) if legal > 0 else 0.0
        d["maidens"] = maidens_map.get(d["id"], 0)
        # wides and noballs are already in dict from the query, but need to be 0 if None
        d["wides"] = d.get("wides") or 0
        d["noballs"] = d.get("noballs") or 0
        stats.append(d)
    return stats


def get_over_summary(innings_id, db_path=None):
    """Get a summary of each over (list of run values per over)."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT over_number, runs, extras, is_wide, is_noball, is_wicket "
        "FROM balls WHERE innings_id = ? ORDER BY over_number, ball_number",
        (innings_id,)
    ).fetchall()
    conn.close()

    overs = {}
    for r in rows:
        r = dict(r)
        on = r["over_number"]
        if on not in overs:
            overs[on] = {"balls": [], "total": 0}
        ball_runs = r["runs"] + r["extras"]
        label = str(ball_runs)
        if r["is_wicket"]:
            label = "W"
        elif r["is_wide"]:
            label = f"Wd+{r['extras']}" if r["extras"] > 1 else "Wd"
        elif r["is_noball"]:
            label = f"Nb+{r['runs']}"
        overs[on]["balls"].append(label)
        overs[on]["total"] += ball_runs
    return overs


# ─── Partnerships ────────────────────────────────────────────

def create_partnership(innings_id, batsman1_id, batsman2_id, db_path=None):
    """Create a new active partnership."""
    conn = get_connection(db_path)
    c = conn.cursor()
    c.execute(
        "INSERT INTO partnerships (innings_id, batsman1_id, batsman2_id) VALUES (?, ?, ?)",
        (innings_id, batsman1_id, batsman2_id)
    )
    pid = c.lastrowid
    conn.commit()
    conn.close()
    return pid


def update_partnership(partnership_id, runs_add=0, balls_add=0, is_active=None, db_path=None):
    """Update partnership stats."""
    conn = get_connection(db_path)
    parts = []
    vals = []
    if runs_add:
        parts.append("runs = runs + ?")
        vals.append(runs_add)
    if balls_add:
        parts.append("balls = balls + ?")
        vals.append(balls_add)
    if is_active is not None:
        parts.append("is_active = ?")
        vals.append(int(is_active))
    if parts:
        vals.append(partnership_id)
        conn.execute(f"UPDATE partnerships SET {', '.join(parts)} WHERE id = ?", vals)
        conn.commit()
    conn.close()


def get_active_partnership(innings_id, db_path=None):
    """Get the current active partnership."""
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM partnerships WHERE innings_id = ? AND is_active = 1 "
        "ORDER BY id DESC LIMIT 1",
        (innings_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_partnerships(innings_id, db_path=None):
    """Get all partnerships for an innings."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT p.*, p1.name as bat1_name, p2.name as bat2_name "
        "FROM partnerships p "
        "JOIN players p1 ON p.batsman1_id = p1.id "
        "JOIN players p2 ON p.batsman2_id = p2.id "
        "WHERE p.innings_id = ? ORDER BY p.id",
        (innings_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_fall_of_wickets(innings_id, db_path=None):
    """Get the fall of wickets data for an innings."""
    conn = get_connection(db_path)
    rows = conn.execute("""
        WITH BallScores AS (
            SELECT b.id, b.over_number, b.ball_number, b.is_wicket, b.out_batsman_id, b.wicket_type,
                   SUM(b.runs + b.extras) OVER (ORDER BY b.id) as current_score,
                   SUM(b.is_wicket) OVER (ORDER BY b.id) as current_wickets
            FROM balls b
            WHERE b.innings_id = ?
        )
        SELECT bs.current_score, bs.current_wickets, bs.over_number, bs.ball_number, p.name as out_name
        FROM BallScores bs
        JOIN players p ON bs.out_batsman_id = p.id
        WHERE bs.is_wicket = 1 AND bs.wicket_type != 'retired hurt'
        ORDER BY bs.id
    """, (innings_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_top_stats(match_id, db_path=None):
    """Get top scorer and best bowler for a match."""
    conn = get_connection(db_path)
    innings = conn.execute("SELECT id FROM innings WHERE match_id = ?", (match_id,)).fetchall()
    conn.close()
    
    top_scorer = None
    best_bowler = None
    
    for inn in innings:
        inn_id = inn["id"]
        # Top Scorer
        bat_stats = get_batting_stats(inn_id, db_path)
        for bs in bat_stats:
            if not top_scorer or bs["runs"] > top_scorer["runs"]:
                top_scorer = bs
                
        # Best Bowler
        bowl_stats = get_bowling_stats(inn_id, db_path)
        for bw in bowl_stats:
            if not best_bowler:
                best_bowler = bw
            elif bw["wickets"] > best_bowler["wickets"]:
                best_bowler = bw
            elif bw["wickets"] == best_bowler["wickets"] and bw["runs_conceded"] < best_bowler["runs_conceded"]:
                best_bowler = bw
                
    return {"top_scorer": top_scorer, "best_bowler": best_bowler}

def get_extras_summary(innings_id, db_path=None):
    """Get extras breakdown for an innings."""
    conn = get_connection(db_path)
    row = conn.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN is_wide = 1 THEN extras ELSE 0 END), 0) as wides,
            COALESCE(SUM(CASE WHEN is_noball = 1 THEN extras ELSE 0 END), 0) as noballs,
            COALESCE(SUM(CASE WHEN is_bye = 1 THEN extras ELSE 0 END), 0) as byes,
            COALESCE(SUM(extras), 0) as total
        FROM balls WHERE innings_id = ?
    """, (innings_id,)).fetchone()
    conn.close()
    d = dict(row) if row else {"wides": 0, "noballs": 0, "byes": 0, "total": 0}
    return d


# Initialize DB on import
init_db()
