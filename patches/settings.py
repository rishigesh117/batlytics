"""Batlytics — Settings Screen"""
from kivy.uix.screenmanager import Screen
import database as db
import os


class SettingsScreen(Screen):


    def clear_history(self):
        """Clear all match history by resetting the database."""
        if os.path.exists(db.DB_PATH):
            os.remove(db.DB_PATH)
            db.init_db()

    def go_home(self):
        self.manager.transition.direction = 'right'
        self.manager.current = 'home'
