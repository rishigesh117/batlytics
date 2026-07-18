"""
Batlytics — Voice Input Handler
Speech recognition for hands-free scoring.
"""
import threading


# Voice command mappings
VOICE_COMMANDS = {
    "zero": {"action": "runs", "value": 0},
    "dot": {"action": "runs", "value": 0},
    "dot ball": {"action": "runs", "value": 0},
    "one": {"action": "runs", "value": 1},
    "single": {"action": "runs", "value": 1},
    "two": {"action": "runs", "value": 2},
    "double": {"action": "runs", "value": 2},
    "three": {"action": "runs", "value": 3},
    "triple": {"action": "runs", "value": 3},
    "four": {"action": "runs", "value": 4},
    "boundary": {"action": "runs", "value": 4},
    "six": {"action": "runs", "value": 6},
    "sixer": {"action": "runs", "value": 6},
    "wicket": {"action": "wicket", "value": 0},
    "out": {"action": "wicket", "value": 0},
    "wide": {"action": "wide", "value": 0},
    "no ball": {"action": "noball", "value": 0},
    "no-ball": {"action": "noball", "value": 0},
    "undo": {"action": "undo", "value": 0},
}


class VoiceInput:
    """Handles voice recognition for scoring commands."""

    def __init__(self, callback=None):
        self.callback = callback
        self.is_listening = False
        self._recognizer = None
        self._microphone = None
        self._available = False
        self._init_recognition()

    def _init_recognition(self):
        """Initialize speech recognition if available."""
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._microphone = sr.Microphone()
            self._available = True
        except (ImportError, OSError):
            self._available = False

    @property
    def available(self):
        return self._available

    def start_listening(self, callback=None):
        """Start listening for voice commands in a background thread."""
        if not self._available:
            return False

        if callback:
            self.callback = callback

        self.is_listening = True
        thread = threading.Thread(target=self._listen_loop, daemon=True)
        thread.start()
        return True

    def stop_listening(self):
        """Stop listening."""
        self.is_listening = False

    def listen_once(self):
        """Listen for a single voice command and return the action."""
        if not self._available:
            return None

        import speech_recognition as sr

        try:
            with self._microphone as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self._recognizer.listen(source, timeout=5, phrase_time_limit=3)

            text = self._recognizer.recognize_google(audio).lower().strip()
            return self._parse_command(text)
        except (sr.UnknownValueError, sr.RequestError, sr.WaitTimeoutError):
            return None

    def _listen_loop(self):
        """Continuous listening loop."""
        import speech_recognition as sr

        while self.is_listening:
            try:
                with self._microphone as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    audio = self._recognizer.listen(source, timeout=5, phrase_time_limit=3)

                text = self._recognizer.recognize_google(audio).lower().strip()
                command = self._parse_command(text)
                if command and self.callback:
                    self.callback(command)
            except (sr.UnknownValueError, sr.RequestError, sr.WaitTimeoutError):
                continue
            except Exception:
                break

    def _parse_command(self, text):
        """Parse spoken text into a scoring command."""
        if not text:
            return None

        # Direct match
        if text in VOICE_COMMANDS:
            return VOICE_COMMANDS[text]

        # Partial match
        for keyword, command in VOICE_COMMANDS.items():
            if keyword in text:
                return command

        return None
