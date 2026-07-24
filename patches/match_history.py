"""Batlytics — Match History Screen"""
from kivy.uix.screenmanager import Screen
from kivy.properties import ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.metrics import dp
import database as db


from kivy.graphics import Color, RoundedRectangle
from kivy.uix.behaviors import ButtonBehavior
from datetime import datetime

class ShadowCard(ButtonBehavior, BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = dp(130)
        self.padding = [dp(16), dp(12), dp(16), dp(12)]
        self.spacing = dp(12)
        
        with self.canvas.before:
            # Shadow layers for depth
            Color(0, 0, 0, 0.04)
            self.shadow1 = RoundedRectangle(pos=(self.x, self.y - dp(2)), size=self.size, radius=[dp(12)])
            Color(0, 0, 0, 0.02)
            self.shadow2 = RoundedRectangle(pos=(self.x, self.y - dp(4)), size=self.size, radius=[dp(12)])
            
            # White card background
            Color(1, 1, 1, 1)
            self.bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
            
        self.bind(pos=self._update_rect, size=self._update_rect)
        
    def _update_rect(self, *args):
        self.shadow1.pos = (self.x, self.y - dp(2))
        self.shadow1.size = self.size
        self.shadow2.pos = (self.x, self.y - dp(4))
        self.shadow2.size = self.size
        self.bg.pos = self.pos
        self.bg.size = self.size

class MatchHistoryScreen(Screen):
    matches = ListProperty([])

    def on_enter(self):
        """Load match history."""
        self.matches = db.list_matches()
        self._rebuild_list()

    def _rebuild_list(self):
        """Rebuild the match list."""
        container = self.ids.get("match_list")
        if not container:
            return
        container.clear_widgets()

        if not self.matches:
            container.add_widget(Label(
                text="No matches yet.\nStart your first match!",
                font_size='16sp', color=(0.5, 0.5, 0.5, 1),
                halign='center'
            ))
            return
            
        container.spacing = dp(12) # Increased spacing between cards

        for match in self.matches:
            card = ShadowCard()
            card.bind(on_release=lambda inst, mid=match['id']: self._view_match(mid))

            # Left side: Match Info Box
            info_box = BoxLayout(orientation='vertical', spacing=dp(2))

            # 1. Title (Team A vs Team B)
            title = Label(
                text=f"{match['team_a']} vs {match['team_b']}",
                font_size='18sp', bold=True, color=(0.1, 0.1, 0.1, 1),
                size_hint_y=None, height=dp(24), halign='left',
                text_size=(None, None)
            )
            title.bind(size=title.setter('text_size'))
            info_box.add_widget(title)

            # 2. Match Format, Date & Time
            format_str = f"T{match['overs']}"
            if match['overs'] == 20:
                format_str = "T20"
            elif match['overs'] == 50:
                format_str = "ODI"
                
            date_str = ""
            if match.get('created_at'):
                try:
                    dt = datetime.fromisoformat(match['created_at'])
                    date_str = dt.strftime("%d %b %Y • %I:%M %p")
                except:
                    pass
                    
            meta_text = f"{format_str} • {date_str}" if date_str else format_str
            meta_label = Label(
                text=meta_text,
                font_size='12sp', color=(0.5, 0.5, 0.5, 1),
                size_hint_y=None, height=dp(16), halign='left',
                text_size=(None, None)
            )
            meta_label.bind(size=meta_label.setter('text_size'))
            info_box.add_widget(meta_label)
            
            # Spacer
            info_box.add_widget(Widget(size_hint_y=None, height=dp(4)))

            # 3. Scores
            innings = db.get_innings(match['id'])
            score_box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(32), spacing=dp(2))
            
            if innings:
                for inn in innings:
                    balls = inn['total_overs_balls']
                    team_score = f"{inn['batting_team']:<10} {inn['total_runs']}/{inn['total_wickets']} ({balls // 6}.{balls % 6})"
                    score_label = Label(
                        text=team_score,
                        font_size='13sp', color=(0.3, 0.3, 0.3, 1),
                        size_hint_y=None, height=dp(16), halign='left',
                        text_size=(None, None)
                    )
                    score_label.bind(size=score_label.setter('text_size'))
                    score_box.add_widget(score_label)
            else:
                setup_label = Label(text="Setup in progress", font_size='13sp', color=(0.4, 0.4, 0.4, 1), size_hint_y=None, height=dp(32), halign='left')
                setup_label.bind(size=setup_label.setter('text_size'))
                score_box.add_widget(setup_label)
                
            info_box.add_widget(score_box)
            
            # Spacer
            info_box.add_widget(Widget(size_hint_y=None, height=dp(2)))

            # 4. Result
            if match['status'] == 'completed':
                if match.get('winner') and match.get('win_margin'):
                    res_text = f"{match['winner']} won by {match['win_margin']}"
                else:
                    res_text = "Match Completed"
                res_color = (0.1, 0.6, 0.1, 1) # Green
            elif match['status'] == 'in_progress':
                res_text = "In Progress"
                res_color = (0.9, 0.5, 0.1, 1) # Orange
            else:
                res_text = "Setup"
                res_color = (0.5, 0.5, 0.5, 1)
                
            result = Label(
                text=res_text,
                font_size='13sp', bold=True, color=res_color,
                size_hint_y=None, height=dp(18), halign='left',
                text_size=(None, None)
            )
            result.bind(size=result.setter('text_size'))
            info_box.add_widget(result)

            card.add_widget(info_box)

            # Right side: Download button if completed
            if match['status'] == 'completed':
                from download_icon import DownloadIcon
                from kivy.uix.behaviors import ButtonBehavior
                from kivy.graphics import Color, Ellipse
                
                class DownloadBtn(ButtonBehavior, BoxLayout):
                    def __init__(self, **kwargs):
                        super().__init__(**kwargs)
                        with self.canvas.before:
                            # Premium light blue background for the circular button
                            Color(0.85, 0.93, 1.0, 1)
                            self.bg_rect = Ellipse(pos=self.pos, size=self.size)
                        self.bind(pos=self._update_rect, size=self._update_rect)
                        
                        # Use blue arrow on light blue circle
                        self.add_widget(DownloadIcon(
                            icon_color=[0.1, 0.4, 0.9, 1], 
                            size_hint=(0.45, 0.45),
                            pos_hint={'center_x': 0.5, 'center_y': 0.5}
                        ))
                        
                    def _update_rect(self, *args):
                        self.bg_rect.pos = self.pos
                        self.bg_rect.size = self.size
                
                btn_box = BoxLayout(orientation='vertical', size_hint_x=None, width=dp(50))
                btn_box.add_widget(Widget()) # Top spacer
                
                btn = DownloadBtn(
                    size_hint=(None, None),
                    size=(dp(44), dp(44)),
                    pos_hint={'center_x': 0.5}
                )
                btn.bind(on_release=lambda inst, mid=match['id']: self._download_pdf(mid))
                btn_box.add_widget(btn)
                
                btn_box.add_widget(Widget()) # Bottom spacer
                card.add_widget(btn_box)

            container.add_widget(card)

    def _download_pdf(self, match_id):
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
            from pdf_scorecard import ScorecardPDF
            from share_helper import download_pdf
            from kivy.app import App
            from datetime import datetime
            import os

            try:
                match = db.get_match(match_id)
                date_str = datetime.now().strftime("%Y-%m-%d")
                team_a = match['team_a'].replace(" ", "_")
                team_b = match['team_b'].replace(" ", "_")
                filename = f"{team_a}_vs_{team_b}_{date_str}_Scorecard.pdf"

                # Generate in app private directory first
                app_dir = App.get_running_app().user_data_dir
                if not os.path.exists(app_dir):
                    os.makedirs(app_dir, exist_ok=True)
                filepath = os.path.join(app_dir, filename)

                pdf_gen = ScorecardPDF(match_id)
                pdf_gen.generate(filepath)

                # Verify file was created
                if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                    raise Exception("PDF file was not created successfully")

                res = download_pdf(filepath, filename)

                popup.dismiss()
                if res:
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

    def _view_match(self, match_id):
        """View scorecard for a match."""
        sc = self.manager.get_screen('scorecard')
        sc.match_id = match_id
        sc.previous_screen = 'match_history'
        self.manager.transition.direction = 'left'
        self.manager.current = 'scorecard'

    def go_home(self):
        self.manager.transition.direction = 'right'
        self.manager.current = 'home'
