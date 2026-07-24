"""
Batlytics — Pure-Python PDF Scorecard Generator
Generates cricket scorecards as PDF files without any C-extension dependencies.
Works on Android (ARM) where reportlab/Pillow fail due to missing native .so files.
"""
import os
from datetime import datetime
import database as db
from scoring_engine import ScoringEngine


class _PDFWriter:
    """Minimal PDF writer — produces valid PDF 1.4 files using only pure Python."""

    def __init__(self):
        self._objects = []  # list of bytes for each PDF object
        self._pages = []    # list of page object indices
        self._fonts = {}
        self._current_page_stream = b""
        self._page_width = 595.28   # A4 width in points
        self._page_height = 841.89  # A4 height in points
        self._margin = 40
        self._y = self._page_height - self._margin
        self._font_size = 10
        self._line_height = 14

        # Register built-in fonts
        self._add_font("F1", "Helvetica")
        self._add_font("F2", "Helvetica-Bold")
        self._add_font("F3", "Courier")

    def _add_font(self, name, base_font):
        idx = self._add_object(
            f"<< /Type /Font /Subtype /Type1 /BaseFont /{base_font} >>".encode()
        )
        self._fonts[name] = idx

    def _add_object(self, data):
        self._objects.append(data)
        return len(self._objects)  # 1-based object number

    def _escape_pdf_text(self, text):
        """Escape special PDF string characters."""
        return (text
                .replace("\\", "\\\\")
                .replace("(", "\\(")
                .replace(")", "\\)")
                .replace("\r", "")
                .replace("\n", " "))

    def _text_cmd(self, x, y, text, font="F1", size=10, r=0, g=0, b=0):
        """Generate PDF text drawing commands."""
        escaped = self._escape_pdf_text(text)
        return (
            f"BT\n"
            f"/{font} {size} Tf\n"
            f"{r:.2f} {g:.2f} {b:.2f} rg\n"
            f"{x:.2f} {y:.2f} Td\n"
            f"({escaped}) Tj\n"
            f"ET\n"
        ).encode()

    def _rect_cmd(self, x, y, w, h, r=0.9, g=0.9, b=0.9, fill=True, stroke=False):
        """Generate PDF rectangle drawing commands."""
        cmd = f"{r:.2f} {g:.2f} {b:.2f} rg\n{x:.2f} {y:.2f} {w:.2f} {h:.2f} re\n"
        if fill and stroke:
            cmd += "B\n"
        elif fill:
            cmd += "f\n"
        elif stroke:
            cmd += "S\n"
        return cmd.encode()

    def _line_cmd(self, x1, y1, x2, y2, r=0.8, g=0.8, b=0.8, width=0.5):
        """Generate PDF line drawing commands."""
        return (
            f"{width:.2f} w\n"
            f"{r:.2f} {g:.2f} {b:.2f} RG\n"
            f"{x1:.2f} {y1:.2f} m\n"
            f"{x2:.2f} {y2:.2f} l\n"
            f"S\n"
        ).encode()

    def _check_page(self, needed=30):
        """Start a new page if we're running low on space."""
        if self._y < self._margin + needed:
            self._flush_page()
            self._y = self._page_height - self._margin

    def _flush_page(self):
        """Finish the current page and add it to the document."""
        if not self._current_page_stream:
            return
        stream_data = self._current_page_stream
        stream_obj_idx = self._add_object(
            f"<< /Length {len(stream_data)} >>\nstream\n".encode() +
            stream_data +
            b"\nendstream"
        )
        # Font references
        font_refs = " ".join(f"/{k} {v} 0 R" for k, v in self._fonts.items())
        page_obj_idx = self._add_object(
            f"<< /Type /Page /MediaBox [0 0 {self._page_width:.2f} {self._page_height:.2f}] "
            f"/Contents {stream_obj_idx} 0 R "
            f"/Resources << /Font << {font_refs} >> >> "
            f"/Parent _PAGES_REF_ >>".encode()
        )
        self._pages.append(page_obj_idx)
        self._current_page_stream = b""

    def write_title(self, text, r=0.18, g=0.49, b=0.20):
        """Write a large title."""
        self._check_page(30)
        approx_width = len(text) * 11
        x = (self._page_width - approx_width) / 2
        self._current_page_stream += self._text_cmd(
            x, self._y, text, font="F2", size=20, r=r, g=g, b=b
        )
        self._y -= 28

    def write_subtitle(self, text):
        """Write a centered subtitle."""
        self._check_page(22)
        approx_width = len(text) * 7
        x = (self._page_width - approx_width) / 2
        self._current_page_stream += self._text_cmd(
            x, self._y, text, font="F1", size=13, r=0.33, g=0.33, b=0.33
        )
        self._y -= 20

    def write_info_line(self, label, value):
        self._check_page(16)
        x_label = self._page_width / 2 - 70
        x_val = self._page_width / 2 - 10
        self._current_page_stream += self._text_cmd(
            x_label, self._y, label, font="F2", size=10, r=0.18, g=0.49, b=0.20
        )
        self._current_page_stream += self._text_cmd(
            x_val, self._y, value, font="F1", size=10, r=0.1, g=0.1, b=0.1
        )
        self._y -= 18

    def write_heading(self, text, r=0.18, g=0.49, b=0.20):
        """Write a section heading."""
        self._check_page(25)
        self._y -= 8
        self._current_page_stream += self._text_cmd(
            self._margin, self._y, text, font="F2", size=13, r=r, g=g, b=b
        )
        self._y -= 20

    def write_text(self, text, bold=False, r=0.1, g=0.1, b=0.1, size=10):
        """Write a line of text."""
        self._check_page(16)
        font = "F2" if bold else "F1"
        self._current_page_stream += self._text_cmd(
            self._margin, self._y, text, font=font, size=size, r=r, g=g, b=b
        )
        self._y -= size + 4

    def write_result(self, text):
        """Write the match result in a prominent style."""
        self._check_page(25)
        approx_width = len(text) * 7.5
        x = (self._page_width - approx_width) / 2
        self._current_page_stream += self._text_cmd(
            x, self._y, text, font="F2", size=16,
            r=0.85, g=0.26, b=0.08
        )
        self._y -= 22

    def write_table(self, headers, rows, col_widths=None, header_bg=(0.91, 0.96, 0.91), header_fg=(0.11, 0.37, 0.13)):
        """Write a table with headers, rows, and grid lines."""
        usable = self._page_width - 2 * self._margin
        num_cols = len(headers)
        if col_widths is None:
            col_widths = [usable / num_cols] * num_cols
        # Normalize widths to fit usable area
        total_w = sum(col_widths)
        if total_w > 0:
            col_widths = [w * usable / total_w for w in col_widths]

        row_height = 18
        header_height = 20

        # Check if we need at least header + 2 rows of space
        self._check_page(header_height + row_height * min(3, len(rows) + 1))

        x_start = self._margin
        y_start = self._y

        # Header background
        self._current_page_stream += self._rect_cmd(
            x_start, self._y - header_height, usable, header_height,
            r=header_bg[0], g=header_bg[1], b=header_bg[2]
        )

        # Header text
        x = x_start + 4
        for i, h in enumerate(headers):
            self._current_page_stream += self._text_cmd(
                x, self._y - 14, h, font="F2", size=9,
                r=header_fg[0], g=header_fg[1], b=header_fg[2]
            )
            x += col_widths[i]
        self._y -= header_height

        # Data rows
        for row_idx, row in enumerate(rows):
            self._check_page(row_height + 5)
            # Alternate row background
            if row_idx % 2 == 1:
                self._current_page_stream += self._rect_cmd(
                    x_start, self._y - row_height, usable, row_height,
                    r=0.97, g=0.97, b=0.95
                )

            x = x_start + 4
            for i, cell in enumerate(row):
                cell_text = str(cell) if cell is not None else ""
                # Truncate long text
                if len(cell_text) > 20 and i < 2:
                    cell_text = cell_text[:18] + ".."
                self._current_page_stream += self._text_cmd(
                    x, self._y - 13, cell_text, font="F1", size=8.5,
                    r=0.15, g=0.15, b=0.15
                )
                x += col_widths[i]
            self._y -= row_height

        # Draw grid lines
        y_bottom = self._y
        
        # Horizontal lines (header top, header bottom, then rows)
        cur_y = y_start
        self._current_page_stream += self._line_cmd(x_start, cur_y, x_start + usable, cur_y)
        cur_y -= header_height
        self._current_page_stream += self._line_cmd(x_start, cur_y, x_start + usable, cur_y)
        for _ in rows:
            cur_y -= row_height
            self._current_page_stream += self._line_cmd(x_start, cur_y, x_start + usable, cur_y)
            
        # Vertical lines
        x_line = x_start
        self._current_page_stream += self._line_cmd(x_line, y_start, x_line, y_bottom)
        for w in col_widths:
            x_line += w
            self._current_page_stream += self._line_cmd(x_line, y_start, x_line, y_bottom)

        self._y -= 10

    def write_spacer(self, height=10):
        """Add vertical space."""
        self._y -= height

    def save(self, filepath):
        """Finalize and write the PDF to disk."""
        # Flush the last page
        self._flush_page()

        if not self._pages:
            # No content written — create a blank page
            self._current_page_stream = self._text_cmd(
                self._margin, self._page_height - self._margin,
                "Empty scorecard", font="F1", size=12
            )
            self._flush_page()

        final_objects = []  # list of bytes, index = obj_num - 1
        final_objects.append(b"")  # Pages placeholder
        final_objects.append(b"")  # Catalog placeholder

        # Add existing objects with shifted numbers
        obj_map = {}  # old_obj_num -> new_obj_num
        for old_idx, obj_data in enumerate(self._objects):
            new_num = len(final_objects) + 1
            obj_map[old_idx + 1] = new_num
            final_objects.append(obj_data)

        # Remap page object references
        page_refs = " ".join(f"{obj_map[p]} 0 R" for p in self._pages)

        # Build Pages object (obj 1)
        final_objects[0] = f"<< /Type /Pages /Kids [{page_refs}] /Count {len(self._pages)} >>".encode()

        # Build Catalog (obj 2)
        final_objects[1] = b"<< /Type /Catalog /Pages _PAGES_REF_ >>"

        # Now fix internal references in page objects
        for i, obj_data in enumerate(final_objects):
            # Replace old object references with new ones
            for old_num, new_num in obj_map.items():
                obj_data = obj_data.replace(f"{old_num} 0 R".encode(), f"_REF_{new_num}_".encode())
            # Now replace placeholders with actual references
            for old_num, new_num in obj_map.items():
                obj_data = obj_data.replace(f"_REF_{new_num}_".encode(), f"{new_num} 0 R".encode())
            
            # Replace the pages placeholder
            obj_data = obj_data.replace(b"_PAGES_REF_", b"1 0 R")
            final_objects[i] = obj_data

        # Write PDF
        with open(filepath, "wb") as f:
            f.write(b"%PDF-1.4\n")
            f.write(b"%\xe2\xe3\xcf\xd3\n")  # Binary comment for PDF readers

            offsets = []
            for idx, obj_data in enumerate(final_objects):
                offsets.append(f.tell())
                obj_num = idx + 1
                f.write(f"{obj_num} 0 obj\n".encode())
                f.write(obj_data)
                f.write(b"\nendobj\n\n")

            # Cross-reference table
            xref_offset = f.tell()
            f.write(b"xref\n")
            f.write(f"0 {len(final_objects) + 1}\n".encode())
            f.write(b"0000000000 65535 f \n")
            for offset in offsets:
                f.write(f"{offset:010d} 00000 n \n".encode())

            # Trailer
            f.write(b"trailer\n")
            f.write(f"<< /Size {len(final_objects) + 1} /Root 2 0 R >>\n".encode())
            f.write(b"startxref\n")
            f.write(f"{xref_offset}\n".encode())
            f.write(b"%%EOF\n")

        return filepath


class ScorecardPDF:
    """Generates a professional cricket scorecard PDF."""

    def __init__(self, match_id, db_path=None):
        self.match_id = match_id
        self.db_path = db_path
        self.engine = ScoringEngine(match_id, db_path=db_path)
        self.match = db.get_match(match_id, db_path=db_path)

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
        pdf = _PDFWriter()

        # 1. Header
        pdf.write_title("Batlytics Scorecard")
        match_title = f"{self.match['team_a']} vs {self.match['team_b']}"
        pdf.write_subtitle(match_title)

        # Match info
        date_str = datetime.now().strftime("%d %b %Y, %H:%M")
        pdf.write_spacer(15)
        pdf.write_info_line("Format", f"{self.match['overs']} Overs, {self.match['players_per_team']} Players")
        if self.match.get('toss_winner'):
            pdf.write_info_line("Toss", f"{self.match['toss_winner']} won and chose to {self.match.get('toss_choice', 'bat')}")
        pdf.write_info_line("Date", date_str)
        pdf.write_spacer(20)

        # 2. Result
        result = self.engine.get_match_result()
        if result:
            if result['winner'] != "Tie":
                res_text = f"{result['winner']} Won by {result['margin']}"
            else:
                res_text = "Match Tied"
            pdf.write_result(res_text)

            potm = result.get('potm')
            if potm:
                pdf.write_text(
                    f"Player of the Match: {potm['name']} "
                    f"({potm['bat_runs']} runs in {potm['bat_balls']} balls)",
                    bold=True
                )
            pdf.write_spacer(10)

        # 3. Innings
        innings_list = db.get_innings(self.match_id, db_path=self.db_path)

        for idx, inn in enumerate(innings_list):
            team_name = inn['batting_team']
            overs_balls = inn['total_overs_balls']
            score_str = f"{inn['total_runs']}/{inn['total_wickets']} ({overs_balls // 6}.{overs_balls % 6} ov)"

            pdf.write_heading(f"{team_name} Innings - {score_str}")

            # Batting Table
            bat_headers = ["Batter", "Status", "R", "B", "4s", "6s", "SR"]
            bat_rows = []
            stats = db.get_batting_stats(inn['id'], db_path=self.db_path)
            for s in stats:
                balls_faced = s.get('balls_faced', 0)
                sr = f"{(s['runs'] / balls_faced * 100):.1f}" if balls_faced > 0 else "0.0"
                if not s['is_out']:
                    status = "not out"
                else:
                    how = s.get('how_out', '')
                    if how in ('bowled', 'lbw', 'hit wicket'):
                        status = f"b {s.get('bowler_name', '')}"
                    elif how == 'caught':
                        status = f"c {s.get('fielder_name', '')} b {s.get('bowler_name', '')}"
                    elif how == 'run out':
                        status = f"run out ({s.get('fielder_name', '')})"
                    else:
                        status = how or "out"

                bat_rows.append([
                    s['name'], status, str(s['runs']), str(balls_faced),
                    str(s['fours']), str(s['sixes']), sr
                ])

            bat_widths = [110, 140, 35, 35, 35, 35, 55]
            pdf.write_table(bat_headers, bat_rows, col_widths=bat_widths)

            # Extras
            try:
                conn = db.get_connection(self.db_path)
                extras_query = conn.execute(
                    "SELECT SUM(extras), SUM(is_wide), SUM(is_noball), SUM(is_legbye), SUM(is_bye) "
                    "FROM balls WHERE innings_id = ?",
                    (inn['id'],)
                ).fetchone()
                conn.close()
                ext_total = extras_query[0] or 0
                wd = extras_query[1] or 0
                nb = extras_query[2] or 0
                lb = extras_query[3] or 0
                by = extras_query[4] or 0
                pdf.write_text(f"Extras: {ext_total} (wd {wd}, nb {nb}, lb {lb}, b {by})", bold=True)
            except Exception:
                pass

            # Fall of Wickets
            fow_str = self._get_fow_string(inn['id'])
            pdf.write_text(f"Fall of Wickets: {fow_str}", size=8.5)
            pdf.write_spacer(10)

            # Bowling Table
            bowl_headers = ["Bowler", "O", "M", "R", "W", "ECON", "WD", "NB"]
            bowl_rows = []
            bowl_stats = db.get_bowling_stats(inn['id'], db_path=self.db_path)
            for bw in bowl_stats:
                bowl_rows.append([
                    bw['name'],
                    str(bw.get('overs', '0')),
                    str(bw.get('maidens', 0)),
                    str(bw.get('runs_conceded', 0)),
                    str(bw.get('wickets', 0)),
                    str(bw.get('economy', '0.0')),
                    str(bw.get('wides', 0)),
                    str(bw.get('noballs', 0))
                ])

            bowl_widths = [110, 40, 40, 40, 40, 50, 40, 40]
            pdf.write_table(
                bowl_headers, 
                bowl_rows, 
                col_widths=bowl_widths,
                header_bg=(1.0, 0.95, 0.88),
                header_fg=(0.9, 0.32, 0.0)
            )
            pdf.write_spacer(15)

        # Footer
        pdf.write_spacer(10)
        pdf.write_text("Generated by Batlytics - Smart Gully Cricket Scoring",
                       r=0.5, g=0.5, b=0.5, size=8)

        pdf.save(output_path)
        return output_path
