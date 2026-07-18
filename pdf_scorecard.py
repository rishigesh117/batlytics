import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import database as db
from scoring_engine import ScoringEngine

class ScorecardPDF:
    def __init__(self, match_id, db_path=None):
        self.match_id = match_id
        self.db_path = db_path
        self.engine = ScoringEngine(match_id, db_path=db_path)
        self.match = db.get_match(match_id, db_path=db_path)
        
        # Styles
        self.styles = getSampleStyleSheet()
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#2e7d32'),
            spaceAfter=10
        )
        self.subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#555555'),
            alignment=1, # center
            spaceAfter=20
        )
        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2e7d32'),
            spaceBefore=15,
            spaceAfter=10
        )
        self.normal_style = self.styles['Normal']
        self.result_style = ParagraphStyle(
            'ResultStyle',
            parent=self.styles['Normal'],
            fontSize=16,
            bold=True,
            textColor=colors.HexColor('#d84315'),
            alignment=1,
            spaceBefore=10,
            spaceAfter=20
        )

    def _get_fow_string(self, innings_id):
        balls = db.get_balls(innings_id, db_path=self.db_path)
        fow = []
        runs = 0
        wickets = 0
        for b in balls:
            runs += b["runs"] + b["extras"]
            if b["is_wicket"] and b.get("wicket_type") != "retired hurt":
                wickets += 1
                overs = b["over_number"] + (b["ball_number"] + 1) / 10.0
                player = b.get("out_batsman_id") or b["batsman_id"]
                player_name = db.get_player(player, db_path=self.db_path)["name"] if player else "Unknown"
                fow.append(f"{runs}-{wickets} ({player_name}, {overs} ov)")
        return " | ".join(fow) if fow else "None"

    def generate(self, output_path):
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )
        elements = []

        # 1. Header
        app_name = "Batlytics Scorecard"
        match_title = f"{self.match['team_a']} vs {self.match['team_b']}"
        date_str = datetime.now().strftime("%d %b %Y, %H:%M")
        
        elements.append(Paragraph(app_name, self.title_style))
        elements.append(Paragraph(match_title, self.subtitle_style))
        
        # Match Info Table
        info_data = [
            ["Format", f"{self.match['overs']} Overs, {self.match['players_per_team']} Players"],
            ["Toss", f"{self.match['toss_winner']} won and chose to {self.match['toss_choice']}"],
            ["Date", date_str]
        ]
        t = Table(info_data, colWidths=[100, 350])
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#2e7d32')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 10))

        # 2. Result
        result = self.engine.get_match_result()
        if result:
            res_text = f"{result['winner']} Won by {result['margin']}" if result['winner'] != "Tie" else "Match Tied"
            elements.append(Paragraph(res_text, self.result_style))

            potm = result.get('potm')
            if potm:
                potm_text = f"<b>Player of the Match:</b> {potm['name']} ({potm['bat_runs']} runs in {potm['bat_balls']} balls)"
                elements.append(Paragraph(potm_text, self.normal_style))
                elements.append(Spacer(1, 15))

        # 3. Innings
        innings_list = db.get_innings(self.match_id, db_path=self.db_path)
        
        for idx, inn in enumerate(innings_list):
            team_name = inn['batting_team']
            score_str = f"{inn['total_runs']}/{inn['total_wickets']} ({inn['total_overs_balls']//6}.{inn['total_overs_balls']%6} ov)"
            
            elements.append(Paragraph(f"{team_name} Innings - {score_str}", self.heading_style))
            
            # Batting Table
            batting_data = [["Batter", "Status", "R", "B", "4s", "6s", "SR"]]
            stats = db.get_batting_stats(inn['id'], db_path=self.db_path)
            for s in stats:
                balls = s.get('balls_faced', 0)
                sr = f"{(s['runs']/balls*100):.2f}" if balls > 0 else "0.00"
                if not s['is_out']:
                    status = "not out"
                else:
                    if s['how_out'] in ('bowled', 'lbw', 'hit wicket'):
                        status = f"b {s['bowler_name']}"
                    elif s['how_out'] == 'caught':
                        status = f"c {s['fielder_name']} b {s['bowler_name']}"
                    elif s['how_out'] == 'run out':
                        status = f"run out ({s['fielder_name']})"
                    else:
                        status = s['how_out']
                        
                batting_data.append([
                    s['name'], status, str(s['runs']), str(balls), 
                    str(s['fours']), str(s['sixes']), sr
                ])
            
            bat_t = Table(batting_data, colWidths=[120, 150, 40, 40, 40, 40, 60])
            bat_t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e8f5e9')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#1b5e20')),
                ('ALIGN', (2,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 8),
                ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ]))
            elements.append(bat_t)
            elements.append(Spacer(1, 10))
            
            # Extras & Total
            conn = db.get_connection(self.db_path)
            extras_query = conn.execute(
                "SELECT SUM(extras), SUM(is_wide), SUM(is_noball), SUM(is_legbye), SUM(is_bye) FROM balls WHERE innings_id = ?", 
                (inn['id'],)
            ).fetchone()
            conn.close()
            ext_total, wd, nb, lb, b = extras_query
            ext_total = ext_total or 0
            extras_str = f"<b>Extras:</b> {ext_total} (wd {wd or 0}, nb {nb or 0}, lb {lb or 0}, b {b or 0})"
            
            elements.append(Paragraph(extras_str, self.normal_style))
            
            fow_str = self._get_fow_string(inn['id'])
            elements.append(Paragraph(f"<b>Fall of Wickets:</b> {fow_str}", self.normal_style))
            elements.append(Spacer(1, 15))
            
            # Bowling Table
            bowling_data = [["Bowler", "O", "M", "R", "W", "ECON", "WD", "NB"]]
            bowl_stats = db.get_bowling_stats(inn['id'], db_path=self.db_path)
            for b in bowl_stats:
                overs_str = b['overs']
                econ = str(b['economy'])
                # Some fields might not be returned by get_bowling_stats, use 0
                maidens = b.get('maidens', 0)
                wides = b.get('wides', 0)
                noballs = b.get('noballs', 0)
                runs = b.get('runs_conceded', 0)
                
                bowling_data.append([
                    b['name'], overs_str, str(maidens), str(runs), 
                    str(b['wickets']), econ, str(wides), str(noballs)
                ])
                
            bowl_t = Table(bowling_data, colWidths=[130, 45, 45, 45, 45, 55, 45, 45])
            bowl_t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#fff3e0')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#e65100')),
                ('ALIGN', (1,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 8),
                ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ]))
            elements.append(bowl_t)
            elements.append(Spacer(1, 20))

        doc.build(elements)
        return output_path
