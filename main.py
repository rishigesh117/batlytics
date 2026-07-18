"""
Batlytics — Smart Gully Cricket Scoring
Main application entry point.
"""
import os
import sys
import platform

# Fix for Windows taskbar icon
if platform.system() == 'Windows':
    import ctypes
    myappid = 'batlytics.cricket.scoring.app.v2' # arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kivy.config import Config
# Set mobile-like window size for desktop testing
Config.set('graphics', 'width', '360')
Config.set('graphics', 'height', '640')
Config.set('graphics', 'resizable', 'True')

# Force absolute path for window icon
icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon_small.png')
Config.set('kivy', 'window_icon', icon_path)

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.core.window import Window

# Import all screens
from screens.splash import SplashScreen
from screens.home import HomeScreen
from screens.match_setup import MatchSetupScreen
from screens.toss import TossScreen
from screens.live_scoring import LiveScoringScreen
from screens.scorecard import ScorecardScreen
from screens.match_result import MatchResultScreen
from screens.match_history import MatchHistoryScreen
from screens.settings import SettingsScreen

# Import database to ensure initialization
import database


class BatlyticsApp(App):
    """Batlytics Cricket Scoring Application."""

    title = "Batlytics"
    icon = icon_path

    def build(self):
        # Set window background color (cricket green tint)
        Window.clearcolor = (0.96, 0.96, 0.94, 1)
        Window.softinput_mode = 'pan'

        # Bind keyboard events for back button navigation
        Window.bind(on_keyboard=self.on_keyboard)

        # Load all KV files
        kv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kv')
        kv_files = [
            'splash.kv', 'home.kv', 'match_setup.kv', 'toss.kv',
            'live_scoring.kv', 'scorecard.kv', 'match_result.kv',
            'match_history.kv', 'settings.kv'
        ]
        for kv_file in kv_files:
            kv_path = os.path.join(kv_dir, kv_file)
            if os.path.exists(kv_path):
                Builder.load_file(kv_path)

        # Create screen manager
        sm = ScreenManager(transition=SlideTransition())

        # Add all screens
        sm.add_widget(SplashScreen(name='splash'))
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(MatchSetupScreen(name='match_setup'))
        sm.add_widget(TossScreen(name='toss'))
        sm.add_widget(LiveScoringScreen(name='live_scoring'))
        sm.add_widget(ScorecardScreen(name='scorecard'))
        sm.add_widget(MatchResultScreen(name='match_result'))
        sm.add_widget(MatchHistoryScreen(name='match_history'))
        sm.add_widget(SettingsScreen(name='settings'))

        return sm

    def on_keyboard(self, window, key, scancode, codepoint, modifier):
        # Keycode 27 is Escape in Kivy and corresponds to the physical Android Back button
        if key == 27:
            if not self.root:
                return False

            current = self.root.current

            if current == 'home':
                # Allow app to exit if on home
                return False
            
            # match_setup, match_history, settings -> home
            elif current in ['match_setup', 'match_history', 'settings']:
                self.root.transition.direction = 'right'
                self.root.current = 'home'
                return True
            
            # Toss -> match_setup
            elif current == 'toss':
                toss_screen = self.root.get_screen('toss')
                toss_screen.go_back()
                return True
            
            # Live scoring -> toss
            elif current == 'live_scoring':
                self.root.transition.direction = 'right'
                self.root.current = 'toss'
                return True
            
            # Scorecard -> goes to its previous screen, or home if none
            elif current == 'scorecard':
                self.root.transition.direction = 'right'
                sc = self.root.get_screen('scorecard')
                if hasattr(sc, 'previous_screen') and sc.previous_screen:
                    self.root.current = sc.previous_screen
                else:
                    self.root.current = 'home'
                return True

            # Match result -> home (match is finished)
            elif current == 'match_result':
                self.root.transition.direction = 'right'
                self.root.current = 'home'
                return True
            
            # For splash screen or any unknown screen mid-transition, consume event but do nothing
            return True
            
        return False


if __name__ == '__main__':
    BatlyticsApp().run()
