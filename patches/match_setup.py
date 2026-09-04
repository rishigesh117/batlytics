"""Batlytics — Match Setup Screen"""
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty, NumericProperty, ListProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.metrics import dp
from kivy.uix.modalview import ModalView
from kivy.uix.button import Button
from kivy.uix.label import Label
import database as db


from kivy.uix.dropdown import DropDown
from kivy.clock import Clock
from kivy.properties import ObjectProperty
from kivy.core.window import Window
from kivy.animation import Animation

class AutocompleteInput(TextInput):
    """A TextInput that shows a dropdown of suggestions."""
    suggestions = ListProperty([])
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dropdown = None
        self.multiline = False
        self.write_tab = False
        
    def _create_dropdown(self):
        if self.dropdown:
            return
        self.dropdown = DropDown(auto_width=False, width=self.width)
        self.dropdown.bind(on_select=self._on_dropdown_select)
        
    def _on_dropdown_select(self, instance, text):
        self.text = text
        self.dropdown.dismiss()
        self.focus = False
        
    def on_text(self, instance, value):
        if not self.focus:
            return
            
        self._update_suggestions(value)
        
    def on_focus(self, instance, value):
        if value:
            # Opened focus
            self._update_suggestions(self.text)
        else:
            # Lost focus
            if self.dropdown:
                self.dropdown.dismiss()
                
    def _update_suggestions(self, query):
        if not self.suggestions:
            if self.dropdown:
                self.dropdown.dismiss()
            return
            
        self._create_dropdown()
        self.dropdown.clear_widgets()
        
        query_lower = query.lower().strip()
        count = 0
        
        for name in self.suggestions:
            if query_lower in name.lower() or not query_lower:
                btn = Button(
                    text=name, size_hint_y=None, height=dp(44),
                    background_normal='',
                    background_color=(1, 1, 1, 1),
                    color=(0.1, 0.1, 0.1, 1),
                    font_size='15sp',
                    halign='left',
                    padding=(dp(12), 0)
                )
                btn.bind(size=btn.setter('text_size'))
                btn.bind(on_release=lambda btn: self.dropdown.select(btn.text))
                self.dropdown.add_widget(btn)
                count += 1
                
            if count >= 8: # Limit to 8 suggestions
                break
                
        if count > 0:
            if not self.dropdown.parent:
                self.dropdown.open(self)
        else:
            self.dropdown.dismiss()

    def keyboard_on_key_down(self, window, keycode, text, modifiers):
        """Handle Enter/Next key to move focus to the next input field."""
        key, key_str = keycode
        if key in (13, 271):  # Enter or Numpad Enter
            # Find the next input to focus
            next_input = self._find_next_input()
            if next_input:
                next_input.focus = True
                return True
        return super().keyboard_on_key_down(window, keycode, text, modifiers)

    def _find_next_input(self):
        """Walk up to find the screen's ordered input list and return the next one."""
        # Walk up to find the MatchSetupScreen
        parent = self.parent
        while parent and not isinstance(parent, MatchSetupScreen):
            parent = parent.parent
        if parent and hasattr(parent, '_get_all_inputs'):
            all_inputs = parent._get_all_inputs()
            try:
                idx = all_inputs.index(self)
                if idx + 1 < len(all_inputs):
                    return all_inputs[idx + 1]
            except ValueError:
                pass
        return None


class MatchSetupScreen(Screen):
    team_a_name = StringProperty("")
    team_b_name = StringProperty("")
    num_overs = NumericProperty(20)
    num_players = NumericProperty(11)
    bowler_limit = NumericProperty(4)
    team_a_captain = StringProperty("Captain")
    team_b_captain = StringProperty("Captain")
    team_a_players = ListProperty([])
    team_b_players = ListProperty([])
    team_a_player_names = ListProperty([])
    team_b_player_names = ListProperty([])
    all_player_suggestions = ListProperty([])
    _from_toss_back = BooleanProperty(False)
    _current_match_id = NumericProperty(0)

    _keyboard_height = NumericProperty(0)
    _keyboard_bound = False

    def on_enter(self):
        """Reset form on entry, unless returning from toss."""
        self.all_player_suggestions = db.get_all_player_names()
        
        if self._from_toss_back:
            self._from_toss_back = False
            # Just rebuild the UI from existing data
            self._rebuild_player_inputs()
            self._bind_keyboard()
            return
        
        self.team_a_name = ""
        self.team_b_name = ""
        self.num_overs = 20
        self.num_players = 11
        self.bowler_limit = 4
        self.team_a_captain = "Captain"
        self.team_b_captain = "Captain"
        self.team_a_players = [""] * self.num_players
        self.team_b_players = [""] * self.num_players
        self.team_a_player_names = []
        self.team_b_player_names = []
        self._current_match_id = 0
        self._rebuild_player_inputs()
        self._bind_keyboard()

    def on_leave(self):
        """Unbind keyboard listener when leaving the screen."""
        self._unbind_keyboard()

    def _bind_keyboard(self):
        """Bind keyboard height changes for scroll-into-view behavior."""
        if not self._keyboard_bound:
            Window.bind(on_keyboard_height=self._on_keyboard_height)
            self._keyboard_bound = True

    def _unbind_keyboard(self):
        """Unbind keyboard height listener."""
        if self._keyboard_bound:
            Window.unbind(on_keyboard_height=self._on_keyboard_height)
            self._keyboard_bound = False
            self._keyboard_height = 0

    def _on_keyboard_height(self, window, height):
        """Called when the soft keyboard opens or closes on Android."""
        self._keyboard_height = height
        # Update the bottom padding spacer so content scrolls above keyboard
        keyboard_spacer = self.ids.get('keyboard_spacer')
        if keyboard_spacer:
            keyboard_spacer.height = max(dp(100), height)
        # When keyboard opens, scroll the focused input into view
        if height > 0:
            Clock.schedule_once(self._scroll_to_focused, 0.15)
        else:
            # Keyboard closed — restore spacer
            if keyboard_spacer:
                keyboard_spacer.height = dp(100)

    def _scroll_to_focused(self, dt):
        """Scroll the ScrollView so the currently focused TextInput is visible."""
        # Find the focused widget
        focused = None
        for inp in self._get_all_inputs():
            if inp.focus:
                focused = inp
                break
        
        if focused:
            self._scroll_to_widget(focused)

    def _get_all_inputs(self):
        """Return an ordered list of all TextInput widgets on this screen.
        Order: Team A name, Team B name, then all Team A players, then all Team B players.
        """
        inputs = []
        
        # Team name inputs — find them from the KV ids or walk the tree
        # We'll walk the ScrollView's content
        scroll_view = self.ids.get('setup_scroll')
        if not scroll_view or not scroll_view.children:
            return inputs
        
        content = scroll_view.children[0]
        
        # Collect all TextInput/AutocompleteInput widgets in order
        self._collect_inputs(content, inputs)
        return inputs

    def _collect_inputs(self, widget, result):
        """Recursively collect TextInput widgets in tree order."""
        if isinstance(widget, TextInput):
            result.append(widget)
        if hasattr(widget, 'children'):
            for child in reversed(widget.children):  # reversed because Kivy stores children bottom-to-top
                self._collect_inputs(child, result)

    def _adjust_player_lists(self):
        """Sync the length of player lists to num_players."""
        if len(self.team_a_players) < self.num_players:
            self.team_a_players.extend([""] * (self.num_players - len(self.team_a_players)))
        elif len(self.team_a_players) > self.num_players:
            self.team_a_players = self.team_a_players[:self.num_players]
            
        if len(self.team_b_players) < self.num_players:
            self.team_b_players.extend([""] * (self.num_players - len(self.team_b_players)))
        elif len(self.team_b_players) > self.num_players:
            self.team_b_players = self.team_b_players[:self.num_players]
            
        self._rebuild_player_inputs()

    def autofill_team(self, team_name, team_label):
        """Automatically populate players based on the last match for this team."""
        team_name = team_name.strip()
        if not team_name:
            return
            
        last_players = db.get_team_last_lineup(team_name)
        if not last_players:
            return
            
        # Do not overwrite if the user already typed players, to be safe.
        # Check if the list is completely empty
        if team_label.lower() == 'a':
            if all(not p.strip() for p in self.team_a_players):
                # Copy players over up to num_players limit
                for i in range(min(len(last_players), self.num_players)):
                    self.team_a_players[i] = last_players[i]
                self._rebuild_player_inputs()
                self._sync_captain_lists()
        else:
            if all(not p.strip() for p in self.team_b_players):
                for i in range(min(len(last_players), self.num_players)):
                    self.team_b_players[i] = last_players[i]
                self._rebuild_player_inputs()
                self._sync_captain_lists()

    def _rebuild_player_inputs(self):
        """Rebuild the player name input lists."""
        # Team A
        container_a = self.ids.get("team_a_container")
        if container_a:
            container_a.clear_widgets()
            for i in range(len(self.team_a_players)):
                inp = AutocompleteInput(
                    hint_text=f"Player {i + 1} Name",
                    text=self.team_a_players[i],
                    suggestions=self.all_player_suggestions,
                    size_hint_y=None,
                    height=dp(48),
                    font_size='16sp',
                    background_color=(1, 1, 1, 1),
                    padding=[dp(12), dp(12), dp(12), dp(12)]
                )
                inp.bind(text=lambda inst, val, idx=i: self._update_player_a(idx, val))
                inp.bind(focus=self._on_input_focus)
                container_a.add_widget(inp)

        # Team B
        container_b = self.ids.get("team_b_container")
        if container_b:
            container_b.clear_widgets()
            for i in range(len(self.team_b_players)):
                inp = AutocompleteInput(
                    hint_text=f"Player {i + 1} Name",
                    text=self.team_b_players[i],
                    suggestions=self.all_player_suggestions,
                    size_hint_y=None,
                    height=dp(48),
                    font_size='16sp',
                    background_color=(1, 1, 1, 1),
                    padding=[dp(12), dp(12), dp(12), dp(12)]
                )
                inp.bind(text=lambda inst, val, idx=i: self._update_player_b(idx, val))
                inp.bind(focus=self._on_input_focus)
                container_b.add_widget(inp)

    def _on_input_focus(self, instance, value):
        """When any input gains focus, scroll it into view after a short delay."""
        if value:
            # Schedule scroll after the keyboard has had time to appear
            Clock.schedule_once(lambda dt: self._scroll_to_widget(instance), 0.3)

    def _scroll_to_widget(self, widget):
        """Scroll the ScrollView so the focused TextInput stays clearly visible where typing."""
        scroll_view = self.ids.get('setup_scroll')
        if not scroll_view or not scroll_view.children:
            return

        content = scroll_view.children[0]
        content_height = content.height
        sv_height = scroll_view.height
        scrollable = content_height - sv_height
        if scrollable <= 0:
            return

        # Calculate widget Y position in content coordinates (y=0 is bottom of content)
        widget_win_pos = widget.to_window(0, 0)
        content_win_pos = content.to_window(0, 0)
        widget_y_in_content = widget_win_pos[1] - content_win_pos[1]

        # Calculate scroll_y so the widget lands at ~40% height from bottom of visible ScrollView window
        # scroll_y = 0 means bottom of content, scroll_y = 1 means top of content
        desired_scroll_y = (widget_y_in_content - sv_height * 0.40) / scrollable
        new_scroll_y = max(0.0, min(1.0, desired_scroll_y))

        # Only animate if meaningful change
        if abs(new_scroll_y - scroll_view.scroll_y) < 0.01:
            return

        Animation.cancel_all(scroll_view, 'scroll_y')
        anim = Animation(scroll_y=new_scroll_y, duration=0.25, t='out_cubic')
        anim.start(scroll_view)

    def _update_player_a(self, index, value):
        players = list(self.team_a_players)
        players[index] = value
        self.team_a_players = players
        self._sync_captain_lists()

    def _update_player_b(self, index, value):
        players = list(self.team_b_players)
        players[index] = value
        self.team_b_players = players
        self._sync_captain_lists()

    def _sync_captain_lists(self):
        """Update dropdown lists for captains."""
        a_names = [p.strip() for p in self.team_a_players if p.strip()]
        if not a_names:
            a_names = ["Captain"]
        self.team_a_player_names = a_names
        if self.team_a_captain not in a_names:
            self.team_a_captain = a_names[0]

        b_names = [p.strip() for p in self.team_b_players if p.strip()]
        if not b_names:
            b_names = ["Captain"]
        self.team_b_player_names = b_names
        if self.team_b_captain not in b_names:
            self.team_b_captain = b_names[0]

    def increase_overs(self):
        if self.num_overs < 50:
            self.num_overs += 1
            self.bowler_limit = max(1, self.num_overs // 5)

    def decrease_overs(self):
        if self.num_overs > 1:
            self.num_overs -= 1
            self.bowler_limit = max(1, self.num_overs // 5)

    def increase_limit(self):
        if self.bowler_limit < self.num_overs:
            self.bowler_limit += 1

    def decrease_limit(self):
        if self.bowler_limit > 1:
            self.bowler_limit -= 1

    def increase_players(self):
        if self.num_players < 11:
            self.num_players += 1
            self._adjust_player_lists()

    def decrease_players(self):
        if self.num_players > 2:
            self.num_players -= 1
            self._adjust_player_lists()

    def _show_error_popup(self, title, message):
        """Show an error popup."""
        popup = ModalView(size_hint=(0.8, None), height=dp(180), background_color=(0, 0, 0, 0.5))
        content = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        content.add_widget(Label(
            text=title, font_size='18sp', bold=True,
            color=(0.9, 0.2, 0.2, 1), size_hint_y=None, height=dp(30)
        ))
        content.add_widget(Label(
            text=message, font_size='14sp', color=(0.2, 0.2, 0.2, 1),
            text_size=(popup.width - dp(40) if popup.width else dp(200), None),
            halign='center'
        ))
        btn = Button(
            text='OK', font_size='16sp', bold=True, size_hint_y=None, height=dp(48),
            background_normal='', background_color=(0.18, 0.49, 0.20, 1), color=(1, 1, 1, 1)
        )
        btn.bind(on_release=popup.dismiss)
        content.add_widget(btn)
        popup.add_widget(content)
        popup.open()

    def _show_numeric_popup(self, title, current_val, min_val, max_val, on_submit):
        """Show a popup to type a numeric value."""
        popup = ModalView(size_hint=(0.8, None), height=dp(200), background_color=(0.12, 0.12, 0.12, 0.95))
        content = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        content.add_widget(Label(
            text=title, font_size='18sp', bold=True,
            color=(1, 1, 1, 1), size_hint_y=None, height=dp(30)
        ))
        text_input = TextInput(
            text=str(current_val), multiline=False, input_filter='int',
            font_size='20sp', halign='center', size_hint_y=None, height=dp(48),
            background_color=(1, 1, 1, 1), padding=[dp(12), dp(12), dp(12), dp(12)]
        )
        content.add_widget(text_input)
        btn_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        cancel_btn = Button(
            text='Cancel', font_size='16sp', bold=True,
            background_normal='', background_color=(0.5, 0.5, 0.5, 1), color=(1, 1, 1, 1)
        )
        ok_btn = Button(
            text='OK', font_size='16sp', bold=True,
            background_normal='', background_color=(0.18, 0.49, 0.20, 1), color=(1, 1, 1, 1)
        )
        cancel_btn.bind(on_release=lambda x: popup.dismiss())
        def _submit(instance):
            try:
                val = int(text_input.text)
                val = max(min_val, min(max_val, val))
                on_submit(val)
            except ValueError:
                pass
            popup.dismiss()
        ok_btn.bind(on_release=_submit)
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(ok_btn)
        content.add_widget(btn_row)
        popup.add_widget(content)
        popup.open()

    def edit_overs(self):
        """Open popup to type overs value."""
        def _set(val):
            self.num_overs = val
            self.bowler_limit = max(1, self.num_overs // 5)
        self._show_numeric_popup('Enter Overs (1-50)', self.num_overs, 1, 50, _set)

    def edit_limit(self):
        """Open popup to type bowler limit value."""
        self._show_numeric_popup('Enter Bowler Limit', self.bowler_limit, 1, self.num_overs, 
                                 lambda val: setattr(self, 'bowler_limit', val))

    def edit_players(self):
        """Open popup to type squad size."""
        def _set(val):
            self.num_players = val
            self._adjust_player_lists()
        self._show_numeric_popup('Enter Squad Size (2-11)', self.num_players, 2, 11, _set)

    def _get_duplicate(self, players):
        seen = set()
        for p in players:
            if p in seen:
                return p
            seen.add(p)
        return None

    def _show_duplicate_warning(self, team_name, player_name, on_allow):
        """Show a warning popup for duplicate players with Allow/Decline options."""
        popup = ModalView(size_hint=(0.85, None), height=dp(200), background_color=(0, 0, 0, 0.5))
        content = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        
        content.add_widget(Label(
            text=f"Duplicate Player in {team_name}", font_size='18sp', bold=True,
            color=(0.9, 0.2, 0.2, 1), size_hint_y=None, height=dp(30)
        ))
        
        # Use self.width or a large fixed width for text_size so it doesn't wrap aggressively
        msg_label = Label(
            text=f"Duplicate player is '{player_name}'.", 
            font_size='15sp', color=(1, 1, 1, 1),
            text_size=(dp(280), None),
            halign='center'
        )
        content.add_widget(msg_label)
        
        btn_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        
        decline_btn = Button(
            text='Decline', font_size='16sp', bold=True,
            background_normal='', background_color=(0.5, 0.5, 0.5, 1), color=(1, 1, 1, 1)
        )
        decline_btn.bind(on_release=popup.dismiss)
        
        def _allow_and_proceed(instance):
            popup.dismiss()
            on_allow()
            
        allow_btn = Button(
            text='Allow', font_size='16sp', bold=True,
            background_normal='', background_color=(0.18, 0.49, 0.20, 1), color=(1, 1, 1, 1)
        )
        allow_btn.bind(on_release=_allow_and_proceed)
        
        btn_row.add_widget(decline_btn)
        btn_row.add_widget(allow_btn)
        content.add_widget(btn_row)
        
        popup.add_widget(content)
        popup.open()

    def proceed_to_toss(self):
        """Validate and create match, then go to toss."""
        # Auto-name teams if left empty
        t_a_name = self.team_a_name.strip() or "Team A"
        t_b_name = self.team_b_name.strip() or "Team B"

        # Auto-name players if left empty
        a_players = []
        for i, p in enumerate(self.team_a_players):
            name = p.strip() or f"Player {i + 1}"
            a_players.append(name)
            
        b_players = []
        for i, p in enumerate(self.team_b_players):
            name = p.strip() or f"Player {i + 1}"
            b_players.append(name)

        # Check for duplicates
        dup_a = self._get_duplicate(a_players)
        if dup_a:
            self._show_duplicate_warning("Team A", dup_a, lambda: self._check_team_b_duplicates(a_players, b_players, t_a_name, t_b_name))
            return
            
        self._check_team_b_duplicates(a_players, b_players, t_a_name, t_b_name)

    def _check_team_b_duplicates(self, a_players, b_players, t_a_name, t_b_name):
        dup_b = self._get_duplicate(b_players)
        if dup_b:
            self._show_duplicate_warning("Team B", dup_b, lambda: self._finalize_match(a_players, b_players, t_a_name, t_b_name))
            return
            
        self._finalize_match(a_players, b_players, t_a_name, t_b_name)

    def _finalize_match(self, a_players, b_players, t_a_name, t_b_name):
        # Create match in DB
        match_id = db.create_match(
            t_a_name,
            t_b_name,
            self.num_overs,
            self.num_players,
            self.bowler_limit,
            self.team_a_captain,
            self.team_b_captain
        )
        self._current_match_id = match_id

        # Add players
        for i, name in enumerate(a_players):
            db.add_player(match_id, t_a_name, name, i + 1)
        for i, name in enumerate(b_players):
            db.add_player(match_id, t_b_name, name, i + 1)

        # Pass match_id to toss screen
        toss_screen = self.manager.get_screen('toss')
        toss_screen.match_id = match_id
        self.manager.transition.direction = 'left'
        self.manager.current = 'toss'
