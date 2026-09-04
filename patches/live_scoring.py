"""Batlytics — Live Match Scoring Screen"""
from kivy.uix.screenmanager import Screen
from kivy.metrics import dp
from kivy.properties import (StringProperty, NumericProperty, BooleanProperty,
                              ListProperty, ObjectProperty)
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
import database as db
from scoring_engine import ScoringEngine
from kivy.graphics import Color, RoundedRectangle

class BallWidget(Label):
    def __init__(self, text, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.font_size = '12sp'
        self.bold = True
        self.size_hint = (None, None)
        self.size = (dp(30), dp(30))
        self.valign = 'middle'
        self.halign = 'center'
        
        bg_color = (0.95, 0.95, 0.95, 1)
        text_color = (0.3, 0.3, 0.3, 1)
        if text == 'W':
            bg_color = (0.9, 0.3, 0.3, 1)
            text_color = (1, 1, 1, 1)
        elif text in ('4', '6'):
            bg_color = (0.12, 0.58, 0.25, 1)
            text_color = (1, 1, 1, 1)
            
        self.color = text_color
        
        with self.canvas.before:
            Color(*bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size


class ExtrasRunsPopup(ModalView):
    """Popup asking how many extra runs were scored with a wide or no ball."""

    def __init__(self, title, callback, run_options=None, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.size_hint = (0.85, 0.45)
        self.background_color = (0, 0, 0, 0.8)
        self.auto_dismiss = False

        if run_options is None:
            run_options = [0, 1, 2, 3, 4]

        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(12))
        layout.add_widget(Label(
            text=title, font_size='18sp', bold=True,
            color=(0.96, 0.49, 0, 1), size_hint_y=None, height=dp(40)
        ))

        grid = GridLayout(cols=3, spacing=dp(10), size_hint_y=None, height=dp(130))
        for r in run_options:
            btn = Button(
                text=str(r), font_size='22sp', bold=True,
                background_normal='',
                background_color=(0.18, 0.49, 0.20, 1),
                color=(1, 1, 1, 1)
            )
            btn.bind(on_release=lambda inst, runs=r: self._select(runs))
            grid.add_widget(btn)
        layout.add_widget(grid)

        cancel_btn = Button(
            text='Cancel', font_size='14sp',
            size_hint_y=None, height=dp(44),
            background_normal='',
            background_color=(0.6, 0.6, 0.6, 1),
            color=(1, 1, 1, 1)
        )
        cancel_btn.bind(on_release=lambda inst: self.dismiss())
        layout.add_widget(cancel_btn)

        self.add_widget(layout)

    def _select(self, runs):
        if self.callback:
            self.callback(runs)
        self.dismiss()

class PlayerSelectPopup(ModalView):
    """Popup for selecting batsman or bowler."""
    title_text = StringProperty("Select Player")
    players = ListProperty([])
    callback = ObjectProperty(None)

    def __init__(self, title, players, callback, **kwargs):
        super().__init__(**kwargs)
        self.title_text = title
        self.players = players
        self.callback = callback
        self.size_hint = (0.85, 0.8)
        self.background_color = (0, 0, 0, 0.7)
        self.auto_dismiss = False
        self._build()

    def _build(self):
        self.layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        self.layout.add_widget(Label(
            text=self.title_text, font_size='20sp', size_hint_y=None,
            height=dp(40), color=(0.18, 0.49, 0.20, 1), bold=True
        ))
        
        # Search Box
        self.search_input = TextInput(
            size_hint_y=None, height=dp(40),
            hint_text='Search player...',
            multiline=False,
            padding=[dp(10), dp(10)]
        )
        self.search_input.bind(text=self._on_search)
        self.layout.add_widget(self.search_input)

        # Scrollable list
        self.scroll = ScrollView(do_scroll_x=False)
        self.grid = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid)
        self.layout.add_widget(self.scroll)
        
        self.add_widget(self.layout)
        self._populate_list(self.players)

    def _on_search(self, instance, text):
        search_text = text.lower()
        filtered = [p for p in self.players if search_text in p["name"].lower()]
        self._populate_list(filtered)
        
    def _populate_list(self, players):
        self.grid.clear_widgets()
        for p in players:
            btn = Button(
                text=p["name"], size_hint_y=None, height=dp(50),
                background_color=(0.18, 0.49, 0.20, 1),
                color=(1, 1, 1, 1), font_size='16sp',
                background_normal=''
            )
            btn.bind(on_release=lambda inst, pid=p["id"]: self._select(pid))
            self.grid.add_widget(btn)

    def _select(self, player_id):
        if self.callback:
            self.callback(player_id)
        self.dismiss()


class InningsBreakPopup(ModalView):
    """Popup shown between innings."""
    target = NumericProperty(0)
    callback = ObjectProperty(None)

    def __init__(self, target, callback, **kwargs):
        super().__init__(**kwargs)
        self.target = target
        self.callback = callback
        self.size_hint = (0.85, 0.4)
        self.background_color = (0, 0, 0, 0.8)
        self.auto_dismiss = False
        self._build()

    def _build(self):
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        
        layout.add_widget(Label(
            text='1ST INNINGS COMPLETE',
            font_size='22sp', bold=True,
            color=(0.18, 0.49, 0.20, 1),
            size_hint_y=None, height=dp(40)
        ))
        
        layout.add_widget(Label(
            text=f'Target: {self.target}',
            font_size='28sp', bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None, height=dp(50),
            halign='center'
        ))
        
        btn = Button(
            text='Start 2nd Innings',
            font_size='18sp', bold=True,
            background_normal='', 
            background_color=(0.18, 0.49, 0.20, 1),
            color=(1, 1, 1, 1),
            size_hint_y=None, height=dp(50)
        )
        btn.bind(on_release=self._start)
        layout.add_widget(btn)
        
        self.add_widget(layout)

    def _start(self, *args):
        if self.callback:
            self.callback()
        self.dismiss()


class LiveScoringScreen(Screen):
    match_id = NumericProperty(0)
    batting_team = StringProperty("")
    bowling_team = StringProperty("")

    # Display properties
    score_text = StringProperty("0/0")
    overs_text = StringProperty("0.0")
    run_rate_text = StringProperty("0.00")
    req_rate_text = StringProperty("")
    innings_label = StringProperty("1ST INNINGS")
    match_title = StringProperty("")

    striker_name = StringProperty("Striker")
    striker_runs = StringProperty("0")
    striker_balls = StringProperty("0")
    striker_4s = StringProperty("0")
    striker_6s = StringProperty("0")
    striker_sr = StringProperty("0.00")
    striker_on_strike = BooleanProperty(True)

    non_striker_name = StringProperty("Non-Striker")
    non_striker_runs = StringProperty("0")
    non_striker_balls = StringProperty("0")
    non_striker_4s = StringProperty("0")
    non_striker_6s = StringProperty("0")
    non_striker_sr = StringProperty("0.00")
    non_striker_on_strike = BooleanProperty(False)

    bowler_name = StringProperty("Bowler")
    bowler_overs = StringProperty("0.0")
    bowler_maidens = StringProperty("0")
    bowler_runs = StringProperty("0")
    bowler_wickets = StringProperty("0")
    bowler_econ = StringProperty("0.00")

    partnership_text = StringProperty("0 (0)")
    recent_balls = ListProperty([])

    target_score = NumericProperty(0)
    runs_needed = NumericProperty(0)
    balls_remaining = NumericProperty(0)
    is_free_hit = BooleanProperty(False)

    engine = None

    def on_enter(self):
        """Initialize match scoring."""
        # Reset engine if we are starting a completely new match
        if self.engine and self.engine.match_id != self.match_id:
            self.engine = None

        if self.match_id and not self.engine:
            self.engine = ScoringEngine(self.match_id)
            match = db.get_match(self.match_id)
            self.match_title = f"{match['team_a']} vs {match['team_b']}"

            if not self.engine.current_innings:
                # Start first innings
                self.engine.start_innings(self.batting_team, self.bowling_team, 1)
                self.innings_label = "1ST INNINGS"
                # Ask for opening batsmen
                Clock.schedule_once(lambda dt: self._select_openers(), 0.5)
            else:
                # Resume match
                if self.engine.innings_number == 1:
                    self.innings_label = "1ST INNINGS"
                else:
                    self.innings_label = "2ND INNINGS"
                self.batting_team = self.engine.current_innings["batting_team"]
                self.bowling_team = self.engine.current_innings["bowling_team"]

        # Try to init voice
        try:
            from voice_input import VoiceInput
            self.voice = VoiceInput()
        except Exception:
            self.voice = None

    def on_recent_balls(self, instance, value):
        """Update recent balls wagon UI."""
        if not hasattr(self, 'ids') or not self.ids.get('recent_balls_container'):
            return
        container = self.ids.recent_balls_container
        container.clear_widgets()
        for ball in value:
            if ball == '|':
                container.add_widget(Label(
                    text='|', color=(0.8, 0.8, 0.8, 1),
                    size_hint_x=None, width=dp(10)
                ))
            else:
                container.add_widget(BallWidget(text=ball))

    def _select_openers(self):
        """Select opening batsmen."""
        players = db.get_players(self.match_id, self.batting_team)
        if len(players) < 2:
            return

        # Select striker
        PlayerSelectPopup(
            "Select Striker",
            players,
            lambda pid: self._set_striker_then_non_striker(pid, players)
        ).open()

    def _set_striker_then_non_striker(self, striker_id, players):
        """After striker is selected, select non-striker."""
        self.engine.striker_id = striker_id
        remaining = [p for p in players if p["id"] != striker_id]
        PlayerSelectPopup(
            "Select Non-Striker",
            remaining,
            lambda pid: self._set_non_striker_then_bowler(striker_id, pid)
        ).open()

    def _set_non_striker_then_bowler(self, striker_id, non_striker_id):
        """After non-striker, select bowler."""
        self.engine.set_openers(striker_id, non_striker_id)
        bowlers = db.get_players(self.match_id, self.bowling_team)
        PlayerSelectPopup(
            "Select Opening Bowler",
            bowlers,
            lambda pid: self._set_bowler(pid)
        ).open()

    def _set_bowler(self, bowler_id):
        self.engine.set_bowler(bowler_id)
        self._refresh_display()

    def _refresh_display(self):
        """Update all display properties from engine state."""
        if not self.engine:
            return

        self.score_text = f"{self.engine.total_runs}/{self.engine.total_wickets}"
        self.overs_text = self.engine.overs_display
        self.run_rate_text = f"{self.engine.run_rate:.2f}"

        # Sync free hit state
        self.is_free_hit = self.engine.is_free_hit

        if self.engine.target:
            self.target_score = self.engine.target
            self.runs_needed = self.engine.target - self.engine.total_runs
            
            match = db.get_match(self.match_id)
            max_overs = match['overs'] if match else 20
            total_legal_balls = self.engine.legal_balls
            self.balls_remaining = (max_overs * 6) - total_legal_balls
            
            rr = self.engine.required_rate
            self.req_rate_text = f"RRR: {rr:.2f}" if rr else ""
        else:
            self.target_score = 0
            self.runs_needed = 0
            self.balls_remaining = 0
            self.req_rate_text = ""

        # Batsman stats
        if self.engine.striker_id:
            p = db.get_player(self.engine.striker_id)
            if p:
                self.striker_name = p["name"]
                stats = self._get_batsman_ball_stats(self.engine.striker_id)
                self.striker_runs = str(stats['runs'])
                self.striker_balls = str(stats['balls'])
                self.striker_4s = str(stats['fours'])
                self.striker_6s = str(stats['sixes'])
                self.striker_sr = f"{stats['sr']:.2f}"
                self.striker_on_strike = True
        else:
            self.striker_name = ""
            self.striker_on_strike = False

        if self.engine.non_striker_id:
            p = db.get_player(self.engine.non_striker_id)
            if p:
                self.non_striker_name = p["name"]
                stats = self._get_batsman_ball_stats(self.engine.non_striker_id)
                self.non_striker_runs = str(stats['runs'])
                self.non_striker_balls = str(stats['balls'])
                self.non_striker_4s = str(stats['fours'])
                self.non_striker_6s = str(stats['sixes'])
                self.non_striker_sr = f"{stats['sr']:.2f}"
                self.non_striker_on_strike = False
        else:
            self.non_striker_name = ""
            self.non_striker_on_strike = False

        # Bowler stats
        if self.engine.bowler_id:
            p = db.get_player(self.engine.bowler_id)
            if p:
                self.bowler_name = p["name"]
                stats = self._get_bowler_ball_stats(self.engine.bowler_id)
                self.bowler_overs = f"{stats['legal'] // 6}.{stats['legal'] % 6}"
                self.bowler_maidens = str(stats['maidens'])
                self.bowler_runs = str(stats['runs'])
                self.bowler_wickets = str(stats['wickets'])
                self.bowler_econ = f"{stats['econ']:.2f}"
        else:
            self.bowler_name = ""

        # Partnership
        partnership = db.get_active_partnership(self.engine.innings_id)
        if partnership:
            self.partnership_text = f"{partnership['runs']} ({partnership['balls']})"

        # Last overs summary (Wagon Style)
        over_summary = db.get_over_summary(self.engine.innings_id)
        if over_summary:
            last_keys = sorted(over_summary.keys())[-2:]  # show max 2 overs
            balls_wagon = []
            for k in last_keys:
                ov = over_summary[k]
                balls_wagon.extend(ov['balls'])
                balls_wagon.append("|")
            
            if balls_wagon and balls_wagon[-1] == "|":
                balls_wagon.pop()
            
            self.recent_balls = balls_wagon
        else:
            self.recent_balls = []

    def _get_batsman_ball_stats(self, batsman_id):
        """Quick batsman stats from balls."""
        balls = db.get_balls(self.engine.innings_id)
        runs = 0
        faced = 0
        fours = 0
        sixes = 0
        for b in balls:
            if b["batsman_id"] == batsman_id:
                if not b["is_wide"]:
                    faced += 1
                    runs += b["runs"]
                    if b["runs"] == 4: fours += 1
                    elif b["runs"] == 6: sixes += 1
        sr = (runs / faced * 100) if faced > 0 else 0.0
        return {"runs": runs, "balls": faced, "fours": fours, "sixes": sixes, "sr": sr}

    def _get_bowler_ball_stats(self, bowler_id):
        """Quick bowler stats from balls."""
        balls = db.get_balls(self.engine.innings_id)
        legal = 0
        runs = 0
        wickets = 0
        maidens = 0
        
        # Calculate maidens properly
        overs_runs = {}
        
        for b in balls:
            if b["bowler_id"] == bowler_id:
                ball_runs = b["runs"] + b["extras"]
                runs += ball_runs
                if not b["is_wide"] and not b["is_noball"]:
                    legal += 1
                if b["is_wicket"] and b["wicket_type"] not in ('run out', 'retired hurt', 'retired out', 'obstructing field', 'timed out'):
                    wickets += 1
                    
                over_num = b["over_number"]
                if over_num not in overs_runs:
                    overs_runs[over_num] = {"runs": 0, "legal": 0}
                overs_runs[over_num]["runs"] += ball_runs
                if not b["is_wide"] and not b["is_noball"]:
                    overs_runs[over_num]["legal"] += 1
                    
        for ov_stats in overs_runs.values():
            if ov_stats["legal"] == 6 and ov_stats["runs"] == 0:
                maidens += 1
                
        overs = legal / 6.0
        econ = (runs / overs) if overs > 0 else 0.0
        
        return {"legal": legal, "runs": runs, "wickets": wickets, "maidens": maidens, "econ": econ}

    # ─── Scoring Actions ─────────────────────────────────────

    def score_runs(self, runs):
        """Record a normal run delivery."""
        result = self.engine.record_ball(runs=runs)
        self._handle_events(result.get("events", []))
        self._refresh_display()

    def score_wicket(self):
        """Show wicket type popup before recording."""
        self._show_wicket_type_popup()

    def _show_wicket_type_popup(self):
        """Popup asking how the batsman got out."""
        popup = ModalView(size_hint=(0.85, 0.75), background_color=(0, 0, 0, 0.8), auto_dismiss=False)
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        layout.add_widget(Label(
            text='How Was the Wicket?', font_size='20sp', bold=True,
            color=(0.82, 0.18, 0.18, 1), size_hint_y=None, height=dp(40)
        ))

        # On a free hit, only run out is allowed
        if self.engine and self.engine.is_free_hit:
            wicket_types = [
                ('Run Out', 'run out'),
            ]
        else:
            wicket_types = [
                ('Bowled', 'bowled'),
                ('Caught', 'caught'),
                ('Run Out', 'run out'),
                ('Stumped', 'stumped'),
                ('LBW', 'lbw'),
                ('Hit Wicket', 'hit wicket'),
                ('Retire Hurt', 'retired hurt'),
                ('Retire Out', 'retired out'),
            ]
        for label, wtype in wicket_types:
            btn = Button(
                text=label, size_hint_y=None, height=dp(46),
                background_normal='', background_color=(0.82, 0.18, 0.18, 1),
                color=(1, 1, 1, 1), font_size='16sp', bold=True
            )
            btn.bind(on_release=lambda inst, w=wtype, p=popup: self._on_wicket_type(w, p))
            layout.add_widget(btn)

        popup.add_widget(layout)
        popup.open()

    def _on_wicket_type(self, wicket_type, popup):
        """After selecting wicket type, check if we need fielder selection."""
        popup.dismiss()
        if wicket_type in ('caught', 'stumped'):
            # Ask who fielded the ball (fielding team players)
            fielders = db.get_players(self.match_id, self.bowling_team)
            self._pending_wicket_type = wicket_type
            if wicket_type == 'caught': title = "Who Caught the Ball?"
            else: title = "Who Stumped?"
            PlayerSelectPopup(
                title,
                fielders,
                lambda pid: self._record_wicket_with_fielder(wicket_type, pid)
            ).open()
        elif wicket_type in ('run out', 'retired hurt', 'retired out'):
            self._ask_which_batsman_is_out(wicket_type)
        else:
            # bowled, lbw, hit wicket — record directly
            result = self.engine.record_ball(is_wicket=True, wicket_type=wicket_type)
            self._handle_events(result.get("events", []))
            self._refresh_display()

    def _on_fielder_selected(self, wicket_type, fielder_id):
        self._record_wicket_with_fielder(wicket_type, fielder_id)

    def _ask_which_batsman_is_out(self, wicket_type, fielder_id=None):
        batsmen = []
        if self.engine.striker_id:
            p = db.get_player(self.engine.striker_id)
            if p: batsmen.append(p)
        if self.engine.non_striker_id:
            p = db.get_player(self.engine.non_striker_id)
            if p: batsmen.append(p)
        if batsmen:
            if wicket_type == 'run out':
                title = "Which Batsman is Run Out?"
                PlayerSelectPopup(
                    title,
                    batsmen,
                    lambda pid: self._ask_run_out_runs(pid)
                ).open()
            else:
                title = "Which Batsman is Retiring?"
                PlayerSelectPopup(
                    title,
                    batsmen,
                    lambda pid: self._record_wicket_specific_batsman(wicket_type, pid, fielder_id)
                ).open()

    def _ask_run_out_runs(self, out_batsman_id):
        """Ask how many completed runs were taken before run out."""
        ExtrasRunsPopup(
            "Completed runs before wicket?",
            lambda runs: self._record_run_out(runs, out_batsman_id),
            run_options=[0, 1, 2, 3, 4, 5]
        ).open()

    def _record_run_out(self, completed_runs, out_batsman_id):
        result = self.engine.record_ball(
            runs=completed_runs, is_wicket=True, wicket_type='run out',
            out_batsman_id=out_batsman_id
        )
        self._handle_events(result.get("events", []))
        self._refresh_display()

    def _record_wicket_with_fielder(self, wicket_type, fielder_id):
        """Record a caught or stumped wicket with the fielder who caught it."""
        result = self.engine.record_ball(
            is_wicket=True, wicket_type=wicket_type, fielder_id=fielder_id
        )
        self._handle_events(result.get("events", []))
        self._refresh_display()

    def _record_wicket_specific_batsman(self, wicket_type, out_batsman_id, fielder_id=None):
        """Record a wicket specifying which batsman is out (e.g. run out, retired)."""
        if wicket_type == 'retired hurt':
            # Retire hurt: record as a special ball but don't count as wicket
            result = self.engine.record_ball(
                runs=0, is_wicket=True, wicket_type='retired hurt',
                out_batsman_id=out_batsman_id
            )
            self._handle_events(result.get("events", []))
            self._refresh_display()
            return
        result = self.engine.record_ball(
            is_wicket=True, wicket_type=wicket_type, out_batsman_id=out_batsman_id, fielder_id=fielder_id
        )
        self._handle_events(result.get("events", []))
        self._refresh_display()

    def score_wide(self):
        """Show popup asking for extra runs with the wide."""
        ExtrasRunsPopup(
            "Wide — Extra runs?",
            self._on_wide_extras,
            run_options=[0, 1, 2, 3, 4]
        ).open()

    def _on_wide_extras(self, runs):
        """Record a wide ball with extra runs."""
        result = self.engine.record_ball(runs=runs, is_wide=True)
        self._handle_events(result.get("events", []))
        self._refresh_display()

    def score_noball(self):
        """Show popup asking for runs off the no ball."""
        ExtrasRunsPopup(
            "No Ball — Runs scored?",
            self._on_noball_extras,
            run_options=[0, 1, 2, 3, 4, 6]
        ).open()

    def _on_noball_extras(self, runs):
        """Record a no-ball with runs."""
        result = self.engine.record_ball(runs=runs, is_noball=True)
        self._handle_events(result.get("events", []))
        self._refresh_display()

    def undo_ball(self):
        """Undo last ball with confirmation."""
        popup = ModalView(size_hint=(0.8, None), height=dp(180), background_color=(0.12, 0.12, 0.12, 0.95))
        content = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        content.add_widget(Label(
            text='Undo last ball?',
            font_size='20sp',
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(40)
        ))
        btn_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        no_btn = Button(
            text='No', font_size='16sp', bold=True,
            background_normal='', background_color=(0.4, 0.4, 0.4, 1), color=(1, 1, 1, 1)
        )
        yes_btn = Button(
            text='Yes', font_size='16sp', bold=True,
            background_normal='', background_color=(0.85, 0.2, 0.2, 1), color=(1, 1, 1, 1)
        )
        no_btn.bind(on_release=lambda x: popup.dismiss())
        def _do_undo(instance):
            popup.dismiss()
            result = self.engine.undo()
            if not result.get("error"):
                self._refresh_display()
        yes_btn.bind(on_release=_do_undo)
        btn_row.add_widget(no_btn)
        btn_row.add_widget(yes_btn)
        content.add_widget(btn_row)
        popup.add_widget(content)
        popup.open()



    # ─── Event Handling ──────────────────────────────────────

    def _handle_events(self, events):
        """Process scoring events."""
        event_types = [e["type"] for e in events]
        
        # If innings is complete, ignore other events (like new bowler at end of over)
        if "innings_complete" in event_types:
            Clock.schedule_once(lambda dt: self._handle_innings_complete(), 0.5)
            return

        for event in events:
            if event["type"] == "need_new_batsman":
                Clock.schedule_once(lambda dt: self._select_new_batsman(), 0.3)
            elif event["type"] == "need_new_bowler":
                Clock.schedule_once(lambda dt: self._select_new_bowler(), 0.3)

    def _select_new_batsman(self):
        """Show popup to select new batsman after wicket."""
        available = self.engine.get_available_batsmen()
        if not available:
            return
        PlayerSelectPopup(
            "Select New Batsman",
            available,
            lambda pid: self._on_new_batsman(pid)
        ).open()

    def _on_new_batsman(self, player_id):
        self.engine.new_batsman(player_id)
        self._refresh_display()

    def _select_new_bowler(self):
        """Show popup to select new bowler at over change."""
        available = self.engine.get_available_bowlers()
        if not available:
            return
        PlayerSelectPopup(
            "Select New Bowler",
            available,
            lambda pid: self._set_bowler(pid)
        ).open()

    def _handle_innings_complete(self):
        """Handle end of innings."""
        self.engine.complete_innings()

        if self.engine.innings_number == 1:
            # Need to show break popup before starting 2nd innings
            target = self.engine.total_runs + 1
            popup = InningsBreakPopup(target, self._start_second_innings)
            popup.open()
        else:
            # Match complete — go to result
            self._go_to_result()
            
    def _start_second_innings(self):
        """Called when user clicks start on the break popup."""
        other_bat = self.bowling_team
        other_bowl = self.batting_team
        self.batting_team = other_bat
        self.bowling_team = other_bowl
        self.engine.start_innings(other_bat, other_bowl, 2)
        self.innings_label = "2ND INNINGS"

        # Load batting order for 2nd innings
        batting_players = db.get_players(self.match_id, other_bat)
        self.engine.batsmen_order = [p["id"] for p in batting_players]

        # Select openers for 2nd innings
        Clock.schedule_once(lambda dt: self._select_openers(), 0.5)
        self._refresh_display()

    def _go_to_result(self):
        """Navigate to match result screen."""
        result_screen = self.manager.get_screen('match_result')
        result_screen.match_id = self.match_id
        self.manager.transition.direction = 'left'
        self.manager.current = 'match_result'

    def go_scorecard(self):
        """Navigate to scorecard."""
        sc = self.manager.get_screen('scorecard')
        sc.match_id = self.match_id
        sc.previous_screen = 'live_scoring'
        self.manager.transition.direction = 'left'
        self.manager.current = 'scorecard'

    def go_back(self):
        """Navigate back to the toss screen."""
        self.manager.transition.direction = 'right'
        self.manager.current = 'toss'

    def cancel_match(self):
        """Show confirmation popup to cancel match and return to home."""
        popup = ModalView(size_hint=(0.85, 0.35), background_color=(0, 0, 0, 0.7))
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))

        layout.add_widget(Label(
            text='Cancel Match?',
            font_size='20sp', bold=True,
            color=(0.82, 0.18, 0.18, 1),
            size_hint_y=None, height=dp(40)
        ))
        layout.add_widget(Label(
            text='This will end the current match.\nAre you sure?',
            font_size='14sp',
            color=(0.4, 0.4, 0.4, 1),
            size_hint_y=None, height=dp(50),
            halign='center'
        ))

        btn_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        no_btn = Button(
            text='No, Continue', font_size='14sp', bold=True,
            background_normal='', background_color=(0.18, 0.49, 0.20, 1),
            color=(1, 1, 1, 1)
        )
        no_btn.bind(on_release=popup.dismiss)

        yes_btn = Button(
            text='Yes, Cancel', font_size='14sp', bold=True,
            background_normal='', background_color=(0.82, 0.18, 0.18, 1),
            color=(1, 1, 1, 1)
        )
        yes_btn.bind(on_release=lambda inst: self._confirm_cancel(popup))

        btn_row.add_widget(no_btn)
        btn_row.add_widget(yes_btn)
        layout.add_widget(btn_row)

        popup.add_widget(layout)
        popup.open()

    def _confirm_cancel(self, popup):
        """Cancel match and go home."""
        popup.dismiss()
        # Reset engine so a new match can start fresh
        self.engine = None
        self.manager.transition.direction = 'right'
        self.manager.current = 'home'
