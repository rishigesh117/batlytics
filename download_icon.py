from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line
from kivy.metrics import dp
from kivy.properties import ListProperty

class DownloadIcon(Widget):
    icon_color = ListProperty([1, 1, 1, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.update_canvas, size=self.update_canvas, icon_color=self.update_canvas)

    def update_canvas(self, *args):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
            
        with self.canvas:
            Color(*self.icon_color)
            
            cx = self.x + self.width / 2.0
            cy = self.y + self.height / 2.0
            
            # Dimensions
            h = self.height
            w = self.width
            
            thickness = dp(2)
            
            # Stem (vertical line)
            stem_top = cy + h * 0.3
            stem_bot = cy - h * 0.1
            Line(points=[cx, stem_top, cx, stem_bot], width=thickness)
            
            # Arrow head (V shape)
            left_wing_x = cx - w * 0.25
            right_wing_x = cx + w * 0.25
            wing_y = cy + h * 0.1
            
            Line(points=[left_wing_x, wing_y, cx, stem_bot - dp(1)], width=thickness, cap='square')
            Line(points=[right_wing_x, wing_y, cx, stem_bot - dp(1)], width=thickness, cap='square')
            
            # Base horizontal line
            base_y = cy - h * 0.3
            Line(points=[cx - w * 0.3, base_y, cx + w * 0.3, base_y], width=thickness)
