"""
Batlytics — Scoring Engine
Core ball-by-ball match logic with undo support.
"""
import database as db


class ScoringEngine:
    """Manages live match state and ball-by-ball scoring."""

    def __init__(self, match_id, db_path=None):
        self.match_id = match_id
        self.db_path = db_path
        self.match = db.get_match(match_id, db_path=db_path)
        self.current_innings = None
        self.innings_id = None
        self.innings_number = 0

        # Current state
        self.total_runs = 0
        self.total_wickets = 0
        self.legal_balls = 0  # total legal balls bowled
        self.max_overs = self.match["overs"]
        self.max_wickets = self.match["players_per_team"] - 1

        # Active players
        self.striker_id = None
        self.non_striker_id = None
        self.bowler_id = None
        self.current_partnership_id = None

        # Batting order tracking
        self.next_batting_index = 0
        self.batsmen_order = []  # list of player IDs in batting order
        self.used_batsmen = set()
        self.bowlers_used_this_over = set()
        self.last_over_bowler_id = None

        # Target for 2nd innings
        self.target = None

        # Free hit after no ball
        self.is_free_hit = False

        # Retired hurt batsmen (can return)
        self.retired_batsmen = set()

        # Load existing state if match is in progress
        self._load_state()

    def _load_state(self):
        """Rebuild state from database (for resuming matches)."""
        innings_list = db.get_innings(self.match_id, db_path=self.db_path)
        if not innings_list:
            return

        # Find the active (non-complete) innings, or the last one
        for inn in innings_list:
            if not inn["is_complete"]:
                self.current_innings = inn
                break
        if self.current_innings is None and innings_list:
            self.current_innings = innings_list[-1]

        if self.current_innings:
            self.innings_id = self.current_innings["id"]
            self.innings_number = self.current_innings["innings_number"]
            self._rebuild_from_balls()

            # Set target if 2nd innings
            if self.innings_number == 2:
                first = db.get_innings(self.match_id, 1, db_path=self.db_path)
                if first:
                    self.target = first["total_runs"] + 1

    def _rebuild_from_balls(self):
        """Rebuild score state from recorded balls."""
        balls = db.get_balls(self.innings_id, db_path=self.db_path)
        self.total_runs = 0
        self.total_wickets = 0
        self.legal_balls = 0
        self.used_batsmen = set()
        self.retired_batsmen = set()
        self.is_free_hit = False

        for ball in balls:
            self.total_runs += ball["runs"] + ball["extras"]
            if ball["is_wicket"]:
                wtype = ball.get("wicket_type", "")
                if wtype == "retired hurt":
                    # Retired hurt does NOT count as a wicket
                    out_id = ball.get("out_batsman_id") or ball["batsman_id"]
                    self.retired_batsmen.add(out_id)
                else:
                    self.total_wickets += 1
            if not ball["is_wide"] and not ball["is_noball"]:
                self.legal_balls += 1
            self.used_batsmen.add(ball["batsman_id"])

        # Rebuild free hit state: if the last ball was a no ball, next is free hit
        if balls:
            last = balls[-1]
            self.is_free_hit = bool(last["is_noball"])

        # Restore current batsmen from last ball
        if balls:
            last = balls[-1]
            self.bowler_id = last["bowler_id"]
            
            if "next_striker_id" in last and last["next_striker_id"] is not None:
                self.striker_id = last["next_striker_id"]
                self.non_striker_id = last["next_non_striker_id"]
            else:
                # Accurately derive from active partnership and swap rules
                partnership = db.get_active_partnership(self.innings_id, db_path=self.db_path)
                if partnership:
                    is_legal = not last["is_wide"] and not last["is_noball"]
                    swap_for_over = (is_legal and (self.legal_balls % 6 == 0))
                    swap_for_runs = (last["runs"] % 2 == 1)
                    
                    last_striker = last["batsman_id"]
                    last_non_striker = partnership["batsman1_id"] if last_striker == partnership["batsman2_id"] else partnership["batsman2_id"]
                        
                    if swap_for_over != swap_for_runs:
                        self.striker_id = last_non_striker
                        self.non_striker_id = last_striker
                    else:
                        self.striker_id = last_striker
                        self.non_striker_id = last_non_striker
                        
                    # If wicket fell on the last ball, clear the out batsman
                    if last["is_wicket"]:
                        out_id = last.get("out_batsman_id") or last["batsman_id"]
                        if self.striker_id == out_id:
                            self.striker_id = None
                        elif self.non_striker_id == out_id:
                            self.non_striker_id = None
                            
        # Remove returned retired batsmen from retired set
        # If a retired batsman appears as batsman_id on a ball AFTER their retire ball,
        # they have returned
        retired_ids = set()
        returned_ids = set()
        for ball in balls:
            if ball["is_wicket"] and ball.get("wicket_type") == "retired hurt":
                out_id = ball.get("out_batsman_id") or ball["batsman_id"]
                retired_ids.add(out_id)
            elif ball["batsman_id"] in retired_ids:
                returned_ids.add(ball["batsman_id"])
        self.retired_batsmen = retired_ids - returned_ids

        # Restore partnership
        partnership = db.get_active_partnership(self.innings_id, db_path=self.db_path)
        if partnership:
            self.current_partnership_id = partnership["id"]

    @property
    def overs_display(self):
        """Return overs in cricket format e.g. '4.3'."""
        return f"{self.legal_balls // 6}.{self.legal_balls % 6}"

    @property
    def current_over(self):
        """Current over number (0-indexed)."""
        return self.legal_balls // 6

    @property
    def ball_in_over(self):
        """Current ball within the over (0-indexed)."""
        return self.legal_balls % 6

    @property
    def run_rate(self):
        """Current run rate."""
        overs = self.legal_balls / 6
        return round(self.total_runs / overs, 2) if overs > 0 else 0.0

    @property
    def required_rate(self):
        """Required run rate (2nd innings only)."""
        if self.target is None:
            return None
        remaining_runs = self.target - self.total_runs
        remaining_balls = (self.max_overs * 6) - self.legal_balls
        if remaining_balls <= 0:
            return None
        return round((remaining_runs / remaining_balls) * 6, 2)

    def start_innings(self, batting_team, bowling_team, innings_number):
        """Start a new innings."""
        self.innings_number = innings_number
        self.innings_id = db.create_innings(
            self.match_id, batting_team, bowling_team, innings_number,
            db_path=self.db_path
        )
        self.current_innings = db.get_innings(
            self.match_id, innings_number, db_path=self.db_path
        )
        self.total_runs = 0
        self.total_wickets = 0
        self.legal_balls = 0
        self.striker_id = None
        self.non_striker_id = None
        self.bowler_id = None
        self.current_partnership_id = None
        self.used_batsmen = set()
        self.next_batting_index = 0

        # Load batting order
        batting_players = db.get_players(
            self.match_id, batting_team, db_path=self.db_path
        )
        self.batsmen_order = [p["id"] for p in batting_players]

        # Set target for 2nd innings
        if innings_number == 2:
            first = db.get_innings(self.match_id, 1, db_path=self.db_path)
            if first:
                self.target = first["total_runs"] + 1

        # Update match status
        db.update_match(self.match_id, status="live", db_path=self.db_path)

        return self.innings_id

    def set_openers(self, striker_id, non_striker_id):
        """Set the opening batsmen."""
        self.striker_id = striker_id
        self.non_striker_id = non_striker_id
        self.used_batsmen.add(striker_id)
        self.used_batsmen.add(non_striker_id)
        self.next_batting_index = 2

        # Create opening partnership
        self.current_partnership_id = db.create_partnership(
            self.innings_id, striker_id, non_striker_id,
            db_path=self.db_path
        )

    def set_bowler(self, bowler_id):
        """Set the current bowler."""
        self.bowler_id = bowler_id

    def record_ball(self, runs=0, is_wide=False, is_noball=False, is_wicket=False,
                    wicket_type=None, out_batsman_id=None, fielder_id=None):
        """
        Record a ball delivery and update all state.
        Returns dict with ball info and any events (over_complete, innings_complete, etc.)
        """
        if self.is_innings_over():
            return {"error": "Innings is already over"}

        if not self.striker_id or not self.bowler_id:
            return {"error": "Striker or bowler not set"}

        events = []
        extras = 0
        is_legal = True

        # Handle extras
        if is_wide:
            extras = 1 + runs  # wide = 1 extra + any additional runs
            runs_to_batsman = 0
            is_legal = False
        elif is_noball:
            extras = 1  # no-ball = 1 extra
            runs_to_batsman = runs
            is_legal = False  # no-ball does NOT count as a legal delivery
        else:
            extras = 0
            runs_to_batsman = runs

        # Record ball in DB
        over_num = self.current_over
        ball_num = self.ball_in_over

        # Fix: For Run Outs, we can have completed runs even if it's a wicket.
        # Ensure we capture this properly.
        ball_id = db.record_ball(
            innings_id=self.innings_id,
            over_number=over_num,
            ball_number=ball_num,
            batsman_id=self.striker_id,
            bowler_id=self.bowler_id,
            runs=runs_to_batsman if not is_wide else 0,
            extras=extras,
            is_wide=int(is_wide),
            is_noball=int(is_noball),
            is_wicket=int(is_wicket),
            wicket_type=wicket_type,
            out_batsman_id=out_batsman_id or (self.striker_id if is_wicket else None),
            fielder_id=fielder_id,
            db_path=self.db_path
        )

        # Update totals
        total_ball_runs = (runs_to_batsman if not is_wide else 0) + extras
        self.total_runs += total_ball_runs

        if is_legal:
            self.legal_balls += 1
            # Clear free hit after a legal delivery
            was_free_hit = self.is_free_hit
            self.is_free_hit = False

        # Set free hit for the NEXT delivery after a no ball
        if is_noball:
            self.is_free_hit = True

        # Update partnership
        if self.current_partnership_id:
            db.update_partnership(
                self.current_partnership_id,
                runs_add=total_ball_runs,
                balls_add=1 if is_legal else 0,
                db_path=self.db_path
            )

        # Handle strike rotation based on completed runs (even if wicket fell, e.g. run out)
        if runs % 2 == 1:
            self._swap_strike()

        # Handle wicket removal
        if is_wicket:
            dismissed_id = out_batsman_id or self.striker_id

            if wicket_type == "retired hurt":
                self.retired_batsmen.add(dismissed_id)
                events.append({"type": "retired_hurt", "player_id": dismissed_id})
            else:
                self.total_wickets += 1
                events.append({"type": "wicket", "player_id": dismissed_id})

            # Close current partnership
            if self.current_partnership_id:
                db.update_partnership(
                    self.current_partnership_id, is_active=False,
                    db_path=self.db_path
                )

            # Check if innings over (all out)
            if self.total_wickets >= self.max_wickets:
                events.append({"type": "innings_complete", "reason": "all_out"})
            else:
                events.append({"type": "need_new_batsman"})
                
            # Remove the dismissed batsman from the crease
            if self.striker_id == dismissed_id:
                self.striker_id = None
            elif self.non_striker_id == dismissed_id:
                self.non_striker_id = None

        # Check over complete
        if is_legal and self.ball_in_over == 0 and self.legal_balls > 0:
            events.append({"type": "over_complete", "over_number": over_num})
            # Swap strike at end of over ONLY if the innings is not complete
            if self.total_wickets < self.max_wickets:
                self._swap_strike()
            self.last_over_bowler_id = self.bowler_id
            self.bowler_id = None  # needs new bowler
            events.append({"type": "need_new_bowler"})

        # Check overs complete
        if self.legal_balls >= self.max_overs * 6:
            events.append({"type": "innings_complete", "reason": "overs_done"})

        # Check target chased (2nd innings)
        if self.target and self.total_runs >= self.target:
            events.append({"type": "innings_complete", "reason": "target_chased"})

        # Update innings totals in DB
        db.update_innings(
            self.innings_id,
            total_runs=self.total_runs,
            total_wickets=self.total_wickets,
            total_overs_balls=self.legal_balls,
            db_path=self.db_path
        )

        # Save the next state of batsmen for robust undo
        db.update_ball_next_state(ball_id, self.striker_id, self.non_striker_id, db_path=self.db_path)


        return {
            "ball_id": ball_id,
            "runs": total_ball_runs,
            "total_runs": self.total_runs,
            "total_wickets": self.total_wickets,
            "overs": self.overs_display,
            "events": events
        }

    def new_batsman(self, player_id):
        """Bring in a new batsman after a wicket."""
        # Fill whichever spot is empty
        if self.striker_id is None:
            self.striker_id = player_id
        elif self.non_striker_id is None:
            self.non_striker_id = player_id
            
        self.used_batsmen.add(player_id)
        if player_id in self.retired_batsmen:
            self.retired_batsmen.remove(player_id)

        # Create new partnership
        if self.striker_id and self.non_striker_id:
            self.current_partnership_id = db.create_partnership(
                self.innings_id, self.striker_id, self.non_striker_id,
                db_path=self.db_path
            )

    def get_available_batsmen(self):
        """Get batsmen who haven't batted yet, plus retired hurt batsmen."""
        all_players = db.get_players(
            self.match_id,
            self.current_innings["batting_team"],
            db_path=self.db_path
        )
        available = []
        for p in all_players:
            if p["id"] not in self.used_batsmen:
                available.append(p)
            elif p["id"] in self.retired_batsmen:
                # Retired hurt batsmen can return
                p = dict(p)  # make a copy
                p["name"] = p["name"] + " (retired)"
                available.append(p)
        return available

    def get_available_bowlers(self):
        """Get players from bowling team eligible to bowl."""
        bowling_players = db.get_players(
            self.match_id,
            self.current_innings["bowling_team"],
            db_path=self.db_path
        )
        # Get bowler limit from match settings
        bowler_limit = self.match.get("bowler_limit", 4) or 4

        # Calculate how many overs each bowler has bowled
        balls = db.get_balls(self.innings_id, db_path=self.db_path)
        bowler_legal_balls = {}
        for b in balls:
            bid = b["bowler_id"]
            if not b["is_wide"] and not b["is_noball"]:
                bowler_legal_balls[bid] = bowler_legal_balls.get(bid, 0) + 1

        available = []
        for p in bowling_players:
            # Can't bowl consecutive overs
            if p["id"] == self.last_over_bowler_id:
                continue
            # Can't exceed bowler limit
            overs_bowled = bowler_legal_balls.get(p["id"], 0) // 6
            if overs_bowled >= bowler_limit:
                continue
            available.append(p)
        return available

    def undo(self):
        """Undo the last ball."""
        last_ball = db.get_last_ball(self.innings_id, db_path=self.db_path)
        if not last_ball:
            return {"error": "No ball to undo"}

        # If the last ball was a wicket (and NOT retired hurt), handle partnership
        if last_ball["is_wicket"] and last_ball.get("wicket_type") != "retired hurt":
            partnerships = db.get_partnerships(
                self.innings_id, db_path=self.db_path
            )
            if partnerships:
                last_partnership = partnerships[-1]
                out_id = last_ball.get("out_batsman_id") or last_ball["batsman_id"]
                # If the last partnership contains the out_batsman, new_batsman hasn't been called yet.
                if last_partnership["batsman1_id"] == out_id or last_partnership["batsman2_id"] == out_id:
                    db.update_partnership(
                        last_partnership["id"], is_active=True, db_path=self.db_path
                    )
                else:
                    # new_batsman was called. Deactivate the new one and reactivate the previous.
                    db.update_partnership(
                        last_partnership["id"], is_active=False, db_path=self.db_path
                    )
                    if len(partnerships) >= 2:
                        db.update_partnership(
                            partnerships[-2]["id"], is_active=True, db_path=self.db_path
                        )

        # Delete the ball from DB
        db.delete_ball(last_ball["id"], db_path=self.db_path)

        # Rebuild all state from remaining balls
        self._rebuild_from_balls()

        # Update innings totals in DB
        db.update_innings(
            self.innings_id,
            total_runs=self.total_runs,
            total_wickets=self.total_wickets,
            total_overs_balls=self.legal_balls,
            db_path=self.db_path
        )

        return {
            "undone": True,
            "total_runs": self.total_runs,
            "total_wickets": self.total_wickets,
            "overs": self.overs_display
        }

    def _swap_strike(self):
        """Swap striker and non-striker."""
        self.striker_id, self.non_striker_id = self.non_striker_id, self.striker_id

    def is_innings_over(self):
        """Check if current innings is complete."""
        if self.total_wickets >= self.max_wickets:
            return True
        if self.legal_balls >= self.max_overs * 6:
            return True
        if self.target and self.total_runs >= self.target:
            return True
        return False

    def complete_innings(self):
        """Mark current innings as complete."""
        db.update_innings(self.innings_id, is_complete=1, db_path=self.db_path)
        if self.current_innings:
            self.current_innings["is_complete"] = 1

    def get_match_result(self):
        """
        Compute match result after both innings.
        Returns dict with winner, margin, and Player of the Match.
        """
        innings_list = db.get_innings(self.match_id, db_path=self.db_path)
        if len(innings_list) < 2:
            return None

        first = innings_list[0]
        second = innings_list[1]

        first_score = first["total_runs"]
        second_score = second["total_runs"]

        if second_score > first_score:
            winner = second["batting_team"]
            wickets_remaining = self.match["players_per_team"] - 1 - second["total_wickets"]
            margin = f"{wickets_remaining} wickets"
        elif first_score > second_score:
            winner = first["batting_team"]
            margin = f"{first_score - second_score} runs"
        else:
            winner = "Tie"
            margin = "Match tied"

        # Player of the Match
        potm = self._calculate_potm(innings_list)

        # Update match
        db.update_match(
            self.match_id,
            status="completed",
            winner=winner,
            win_margin=margin,
            potm_id=potm["id"] if potm else None,
            db_path=self.db_path
        )

        return {
            "winner": winner,
            "margin": margin,
            "first_innings": {
                "team": first["batting_team"],
                "score": f"{first_score}/{first['total_wickets']}",
                "overs": f"{first['total_overs_balls'] // 6}.{first['total_overs_balls'] % 6}"
            },
            "second_innings": {
                "team": second["batting_team"],
                "score": f"{second_score}/{second['total_wickets']}",
                "overs": f"{second['total_overs_balls'] // 6}.{second['total_overs_balls'] % 6}"
            },
            "potm": potm
        }

    def _calculate_potm(self, innings_list):
        """Calculate Player of the Match based on batting + bowling performance."""
        player_scores = {}

        for inn in innings_list:
            # Batting contributions
            bat_stats = db.get_batting_stats(inn["id"], db_path=self.db_path)
            for bs in bat_stats:
                pid = bs["id"]
                if pid not in player_scores:
                    player_scores[pid] = {
                        "id": pid, "name": bs["name"],
                        "bat_runs": 0, "bat_balls": 0, "bat_sr": 0,
                        "bowl_wickets": 0, "bowl_runs": 0,
                        "fours": 0, "sixes": 0, "score": 0
                    }
                player_scores[pid]["bat_runs"] += bs["runs"]
                player_scores[pid]["bat_balls"] += bs["balls_faced"]
                player_scores[pid]["fours"] += bs["fours"]
                player_scores[pid]["sixes"] += bs["sixes"]

            # Bowling contributions
            bowl_stats = db.get_bowling_stats(inn["id"], db_path=self.db_path)
            for bw in bowl_stats:
                pid = bw["id"]
                if pid not in player_scores:
                    player_scores[pid] = {
                        "id": pid, "name": bw["name"],
                        "bat_runs": 0, "bat_balls": 0, "bat_sr": 0,
                        "bowl_wickets": 0, "bowl_runs": 0,
                        "fours": 0, "sixes": 0, "score": 0
                    }
                player_scores[pid]["bowl_wickets"] += bw["wickets"]
                player_scores[pid]["bowl_runs"] += bw["runs_conceded"]

        # Score formula: batting_sr × runs / 100 + wickets × 25 - bowl_runs / 10
        for pid, ps in player_scores.items():
            sr = (ps["bat_runs"] / ps["bat_balls"] * 100) if ps["bat_balls"] > 0 else 0
            ps["bat_sr"] = round(sr, 1)
            ps["score"] = (sr * ps["bat_runs"] / 100) + (ps["bowl_wickets"] * 25) - (ps["bowl_runs"] / 10)

        if not player_scores:
            return None

        best = max(player_scores.values(), key=lambda x: x["score"])
        return best
