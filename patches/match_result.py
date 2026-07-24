"""Batlytics — Match Result Screen"""
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty, NumericProperty
import database as db
from scoring_engine import ScoringEngine


class MatchResultScreen(Screen):
    match_id = NumericProperty(0)
    winner_text = StringProperty("")
    margin_text = StringProperty("")
    team_a_score = StringProperty("")
    team_b_score = StringProperty("")
    team_a_name = StringProperty("")
    team_b_name = StringProperty("")
    team_a_overs = StringProperty("")
    team_b_overs = StringProperty("")
    potm_name = StringProperty("")
    potm_runs = StringProperty("0")
    potm_balls = StringProperty("0")
    potm_sr = StringProperty("0.0")

    def on_enter(self):
        """Load match result."""
        if not self.match_id:
            return

        engine = ScoringEngine(self.match_id)
        result = engine.get_match_result()

        if not result:
            self.winner_text = "Match Incomplete"
            return

        self.winner_text = result["winner"] + " Won!" if result["winner"] != "Tie" else "Match Tied!"
        self.margin_text = f"by {result['margin']}" if result["winner"] != "Tie" else result["margin"]

        # First innings
        self.team_a_name = result["first_innings"]["team"]
        self.team_a_score = result["first_innings"]["score"]
        self.team_a_overs = result["first_innings"]["overs"]

        # Second innings
        self.team_b_name = result["second_innings"]["team"]
        self.team_b_score = result["second_innings"]["score"]
        self.team_b_overs = result["second_innings"]["overs"]

        # Player of the Match
        potm = result.get("potm")
        if potm:
            self.potm_name = potm["name"]
            self.potm_runs = str(potm["bat_runs"])
            self.potm_balls = str(potm["bat_balls"])
            self.potm_sr = str(potm["bat_sr"])

    def go_home(self):
        self.manager.transition.direction = 'right'
        self.manager.current = 'home'

    def go_scorecard(self):
        sc = self.manager.get_screen('scorecard')
        sc.match_id = self.match_id
        sc.previous_screen = 'match_result'
        self.manager.transition.direction = 'left'
        self.manager.current = 'scorecard'

    def _generate_pdf(self):
        """Generate the scorecard PDF and return (filepath, filename)."""
        import os
        from datetime import datetime
        from kivy.app import App
        from pdf_scorecard import ScorecardPDF

        # Format filename with timestamp to avoid conflicts
        date_str = datetime.now().strftime("%Y-%m-%d")
        timestamp = int(datetime.now().timestamp())
        team_a = self.team_a_name.replace(" ", "_")
        team_b = self.team_b_name.replace(" ", "_")
        filename = f"{team_a}_vs_{team_b}_{date_str}_Scorecard.pdf"

        # Generate in app's private directory first
        app_dir = App.get_running_app().user_data_dir
        if not os.path.exists(app_dir):
            os.makedirs(app_dir, exist_ok=True)
        filepath = os.path.join(app_dir, filename)

        pdf_gen = ScorecardPDF(self.match_id)
        pdf_gen.generate(filepath)

        # Verify file was created
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            raise Exception("PDF file was not created successfully")

        return filepath, filename

    def download_pdf(self):
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label
        from kivy.clock import Clock

        popup = Popup(
            title='Downloading',
            content=Label(text='Generating Scorecard...'),
            size_hint=(0.8, 0.4)
        )
        popup.open()

        def _do_download(dt):
            try:
                filepath, filename = self._generate_pdf()

                from share_helper import download_pdf
                result = download_pdf(filepath, filename)

                popup.dismiss()
                if result:
                    msg = 'Scorecard downloaded successfully!\n\nSaved to Downloads/Batlytics/'
                    succ = Popup(
                        title='Success',
                        content=Label(
                            text=msg, halign='center',
                            valign='middle', text_size=(None, None)
                        ),
                        size_hint=(0.85, 0.35)
                    )
                    succ.content.bind(size=succ.content.setter('text_size'))
                    succ.open()
                else:
                    err = Popup(
                        title='Error',
                        content=Label(text='Unable to save the PDF.\nPlease try again.'),
                        size_hint=(0.8, 0.35)
                    )
                    err.open()
            except Exception as e:
                popup.dismiss()
                import traceback
                traceback.print_exc()
                err = Popup(
                    title='Error',
                    content=Label(
                        text=f'Unable to generate the PDF.\n{str(e)[:100]}',
                        halign='center', text_size=(None, None)
                    ),
                    size_hint=(0.85, 0.35)
                )
                err.content.bind(size=err.content.setter('text_size'))
                err.open()

        Clock.schedule_once(_do_download, 0.2)

    def share_pdf(self):
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label
        from kivy.clock import Clock

        popup = Popup(
            title='Preparing',
            content=Label(text='Generating Scorecard...'),
            size_hint=(0.8, 0.4)
        )
        popup.open()

        def _do_share(dt):
            try:
                filepath, filename = self._generate_pdf()
                popup.dismiss()
                from share_helper import share_pdf
                share_pdf(filepath)
            except Exception as e:
                popup.dismiss()
                err = Popup(
                    title='Error',
                    content=Label(text=f'Unable to share.\n{str(e)[:100]}'),
                    size_hint=(0.8, 0.35)
                )
                err.open()

        Clock.schedule_once(_do_share, 0.2)
