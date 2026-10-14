import json
import os
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import cv2 as cv
import numpy as np
import pygame
 
 
class SecondWindow:
    """A black panel that is stitched next to the camera frame,
    so both live in the same window, each taking half."""
 
    def __init__(self, name="Game", side="right"):
        self.name = name
        self.side = side          # side where the black panel goes
        self.canvas = None        # created on first frame (matches camera size)
        self.frame_width = 0
        self.screen = "name_entry" # start with name entry
        self.player_name = ""
        self.leaderboard_file = "leaderboard.json"
        self.leaderboard = self._load_leaderboard()     # list of tuples: (name, waves)
        self.action = None
        self.buttons = []
        self.mouse_callback_window = None
        self.fullscreen = None
        self.fullscreen_size = None
        self.fullscreen_buffer = None
        self.ready_button = None
        self.countdown_started = None

    def _load_leaderboard(self):
        """Load leaderboard data from external storage."""
        if os.path.exists(self.leaderboard_file):
            try:
                with open(self.leaderboard_file, "r") as f:
                    data = json.load(f)
                    # Convert lists back to tuples if necessary
                    return [(item["name"], item["waves"]) for item in data]
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def save_leaderboard(self):
        """Save leaderboard data to external storage."""
        try:
            data = [{"name": name, "waves": waves} for name, waves in self.leaderboard]
            with open(self.leaderboard_file, "w") as f:
                json.dump(data, f, indent=4)
        except IOError:
            pass

    def add_score(self, name, waves):
        """Add a new score and persist it immediately."""
        self.leaderboard.append((name, waves))
        # Keep sorted by waves descending
        self.leaderboard = sorted(self.leaderboard, key=lambda x: x[1], reverse=True)
        self.save_leaderboard()
 
    def clear(self, frame):
        """Reset the black canvas so it matches the camera frame size."""
        h, w = frame.shape[:2]
        self.frame_width = w
        if self.canvas is None or self.canvas.shape[:2] != (h, w):
            self.canvas = np.zeros((h, w, 3), dtype=np.uint8)
        else:
            self.canvas[:] = 0
 
    def combine(self, frame):
        """Return one image: camera on one half, black canvas on the other."""
        if self.side == "right":
            return np.hstack((frame, self.canvas))
        return np.hstack((self.canvas, frame))
 
    def show(self, frame, window_name="Camera"):
        if self.mouse_callback_window != window_name:
            cv.namedWindow(window_name, cv.WINDOW_NORMAL)
            cv.setMouseCallback(window_name, self._handle_mouse)
            self.mouse_callback_window = window_name

        wants_fullscreen = self.screen in ("ready", "countdown", "play")
        if wants_fullscreen != self.fullscreen:
            mode = cv.WINDOW_FULLSCREEN if wants_fullscreen else cv.WINDOW_NORMAL
            cv.setWindowProperty(window_name, cv.WND_PROP_FULLSCREEN, mode)
            if not wants_fullscreen:
                self.fullscreen_size = None
                self.fullscreen_buffer = None
                view_width = self.frame_width * 2
                cv.resizeWindow(window_name, view_width, self.canvas.shape[0])
            self.fullscreen = wants_fullscreen

        if wants_fullscreen:
            self._refresh_fullscreen_size(window_name)
        cv.imshow(window_name, self.display_frame(frame))

    def _refresh_fullscreen_size(self, window_name):
        if self.fullscreen_size is not None:
            return

        initialized_display_here = not pygame.display.get_init()
        try:
            if initialized_display_here:
                pygame.display.init()
            display_sizes = pygame.display.get_desktop_sizes()
            if display_sizes:
                view_width, view_height = display_sizes[0]
            else:
                view_width = view_height = 0
        except pygame.error:
            view_width = view_height = 0
        finally:
            if initialized_display_here and pygame.display.get_init():
                pygame.display.quit()

        if view_width <= 0 or view_height <= 0:
            try:
                _, _, view_width, view_height = cv.getWindowImageRect(window_name)
            except cv.error:
                return
        if view_width <= 0 or view_height <= 0:
            return
        if self.fullscreen_size != (view_width, view_height):
            self.fullscreen_size = (view_width, view_height)
            self.fullscreen_buffer = np.empty(
                (view_height, view_width, 3), dtype=self.canvas.dtype
            )

    def display_frame(self, frame):
        if self.screen in ("ready", "countdown", "play"):
            if self.fullscreen_size is None:
                return self.canvas
            width, height = self.fullscreen_size
            if (self.fullscreen_buffer is None
                    or self.fullscreen_buffer.shape[:2] != (height, width)):
                self.fullscreen_buffer = np.empty((height, width, 3), dtype=self.canvas.dtype)
            cv.resize(self.canvas, (width, height), dst=self.fullscreen_buffer,
                      interpolation=cv.INTER_LINEAR)
            return self.fullscreen_buffer
        return self.combine(frame)

    def main_menu(self, frame):
        height, width = self.canvas.shape[:2]
        self.buttons = []

        if self.screen == "name_entry":
            self._draw_name_entry(height, width)
            return self._consume_action()

        if self.screen in ("countdown", "play"):
            return self._consume_action()

        if self.screen == "game_over":
            self._draw_game_over(height, width)
            return self._consume_action()

        if self.screen == "ready":
            self._draw_ready_screen(height, width)
            return self._consume_action()

        if self.screen == "leaderboard":
            self._draw_leaderboard_screen(height, width)
            return self._consume_action()

        if self.screen == "controls":
            self._draw_control_guide(height, width)
            button_width = min(180, width - 40)
            button_height = 48
            left = (width - button_width) // 2
            top = height - button_height - 16
            rect = (left, top, left + button_width, top + button_height)
            self.buttons.append((rect, "back"))
            cv.rectangle(self.canvas, rect[:2], rect[2:], (48, 58, 66), -1)
            cv.rectangle(self.canvas, rect[:2], rect[2:], (90, 205, 170), 2)
            label = "Back"
            text_size = cv.getTextSize(label, cv.FONT_HERSHEY_SIMPLEX, 0.65, 2)[0]
            cv.putText(self.canvas, label,
                       (left + (button_width - text_size[0]) // 2,
                        top + (button_height + text_size[1]) // 2),
                       cv.FONT_HERSHEY_SIMPLEX, 0.65, (245, 245, 245), 2, cv.LINE_AA)
            return self._consume_action()

        title = "ZOMBIE SURVIVAL"
        labels = [("Play", "play"), ("Leaderboard", "leaderboard"), ("Controls", "controls"), ("Quit", "quit")]

        button_width = min(260, width - 60)
        button_height = 48
        gap = 14
        total_height = len(labels) * button_height + (len(labels) - 1) * gap
        left = (width - button_width) // 2
        top = (height - total_height) // 2 + 35

        title_size = cv.getTextSize(title, cv.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
        title_x = (width - title_size[0]) // 2
        cv.putText(self.canvas, title, (title_x, max(title_size[1] + 10, top - 20)),
               cv.FONT_HERSHEY_SIMPLEX, 1.0, (235, 240, 245), 2, cv.LINE_AA)

        for index, (label, action) in enumerate(labels):
            y1 = top + index * (button_height + gap)
            rect = (left, y1, left + button_width, y1 + button_height)
            self.buttons.append((rect, action))
            cv.rectangle(self.canvas, rect[:2], rect[2:], (48, 58, 66), -1)
            cv.rectangle(self.canvas, rect[:2], rect[2:], (90, 205, 170), 2)
            text_size = cv.getTextSize(label, cv.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            text_x = left + (button_width - text_size[0]) // 2
            text_y = y1 + (button_height + text_size[1]) // 2
            cv.putText(self.canvas, label, (text_x, text_y),
                       cv.FONT_HERSHEY_SIMPLEX, 0.7, (245, 245, 245), 2, cv.LINE_AA)

        return self._consume_action()

    def _draw_name_entry(self, height, width):
        title = "ENTER YOUR NAME"
        cv.putText(self.canvas, title, ((width - cv.getTextSize(title, cv.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0][0]) // 2, height // 3 - 20),
                   cv.FONT_HERSHEY_SIMPLEX, 0.8, (235, 240, 245), 2, cv.LINE_AA)
        
        box_width = min(280, width - 40)
        box_height = 50
        left = (width - box_width) // 2
        top = height // 3 + 10
        cv.rectangle(self.canvas, (left, top), (left + box_width, top + box_height), (40, 50, 55), -1)
        cv.rectangle(self.canvas, (left, top), (left + box_width, top + box_height), (90, 205, 170), 2)
        
        display_name = self.player_name if self.player_name else "Type name..."
        color = (245, 245, 245) if self.player_name else (120, 130, 135)
        cv.putText(self.canvas, display_name, (left + 15, top + 32),
                   cv.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv.LINE_AA)

        instruction = "Press ENTER when finished"
        cv.putText(self.canvas, instruction, ((width - cv.getTextSize(instruction, cv.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0][0]) // 2, top + box_height + 30),
                   cv.FONT_HERSHEY_SIMPLEX, 0.45, (180, 190, 185), 1, cv.LINE_AA)

    def handle_keyboard_input(self, key):
        if self.screen == "name_entry":
            if key == 13: # Enter key
                if self.player_name.strip():
                    self.screen = "menu"
            elif key == 8: # Backspace
                self.player_name = self.player_name[:-1]
            elif 32 <= key <= 126 and len(self.player_name) < 12:
                self.player_name += chr(key)

    def _draw_game_over(self, height, width):
        title = "GAME OVER"
        title_size = cv.getTextSize(title, cv.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
        cv.putText(self.canvas, title, ((width - title_size[0]) // 2, height // 3 - 20),
                   cv.FONT_HERSHEY_SIMPLEX, 1.0, (50, 60, 255), 2, cv.LINE_AA)

        button_width = min(240, width - 60)
        button_height = 50
        gap = 16
        labels = [("Try Again", "try_again"), ("Quit", "quit")]
        top = height // 2

        for index, (label, action) in enumerate(labels):
            y1 = top + index * (button_height + gap)
            left = (width - button_width) // 2
            rect = (left, y1, left + button_width, y1 + button_height)
            self.buttons.append((rect, action))
            cv.rectangle(self.canvas, rect[:2], rect[2:], (48, 58, 66), -1)
            cv.rectangle(self.canvas, rect[:2], rect[2:], (90, 205, 170), 2)
            text_size = cv.getTextSize(label, cv.FONT_HERSHEY_SIMPLEX, 0.65, 2)[0]
            cv.putText(self.canvas, label,
                       (left + (button_width - text_size[0]) // 2,
                        y1 + (button_height + text_size[1]) // 2),
                       cv.FONT_HERSHEY_SIMPLEX, 0.65, (245, 245, 245), 2, cv.LINE_AA)

    def _draw_leaderboard_screen(self, height, width):
        title = "TOP 5 LEADERBOARD"
        title_size = cv.getTextSize(title, cv.FONT_HERSHEY_SIMPLEX, 0.75, 2)[0]
        cv.putText(self.canvas, title, ((width - title_size[0]) // 2, 45),
                   cv.FONT_HERSHEY_SIMPLEX, 0.75, (235, 240, 245), 2, cv.LINE_AA)

        sorted_lb = self.leaderboard[:5]
        
        y = 90
        if not sorted_lb:
            no_scores = "No games played yet!"
            ns_size = cv.getTextSize(no_scores, cv.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
            cv.putText(self.canvas, no_scores, ((width - ns_size[0]) // 2, height // 2),
                       cv.FONT_HERSHEY_SIMPLEX, 0.5, (180, 190, 185), 1, cv.LINE_AA)
        else:
            for i, (name, waves) in enumerate(sorted_lb):
                text = f"{i+1}. {name} - Wave {waves}"
                cv.putText(self.canvas, text, (40, y),
                           cv.FONT_HERSHEY_SIMPLEX, 0.55, (210, 230, 220), 2, cv.LINE_AA)
                y += 35

        button_width = min(180, width - 40)
        button_height = 45
        left = (width - button_width) // 2
        top = height - button_height - 20
        rect = (left, top, left + button_width, top + button_height)
        self.buttons.append((rect, "back"))
        cv.rectangle(self.canvas, rect[:2], rect[2:], (48, 58, 66), -1)
        cv.rectangle(self.canvas, rect[:2], rect[2:], (90, 205, 170), 2)
        label = "Back"
        text_size = cv.getTextSize(label, cv.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        cv.putText(self.canvas, label,
                   (left + (button_width - text_size[0]) // 2,
                    top + (button_height + text_size[1]) // 2),
                   cv.FONT_HERSHEY_SIMPLEX, 0.6, (245, 245, 245), 2, cv.LINE_AA)

    def _draw_ready_screen(self, height, width):
        self.ready_button = None
        title = "WAVES MODE"
        subtitle = f"Survivor: {self.player_name}"
        instruction = "Place BOTH extended index fingertips on READY"
        center_x = width // 2
        cv.putText(self.canvas, title, (center_x - 125, height // 3),
                   cv.FONT_HERSHEY_SIMPLEX, 1.0, (235, 240, 245), 2, cv.LINE_AA)
        cv.putText(self.canvas, subtitle, (center_x - cv.getTextSize(subtitle, cv.FONT_HERSHEY_SIMPLEX, 0.48, 1)[0][0] // 2, height // 3 + 36),
                   cv.FONT_HERSHEY_SIMPLEX, 0.48, (185, 205, 193), 1, cv.LINE_AA)
        cv.putText(self.canvas, instruction, (center_x - 178, height // 2 + 3),
                   cv.FONT_HERSHEY_SIMPLEX, 0.46, (215, 225, 215), 1, cv.LINE_AA)

        button_width = min(270, width - 48)
        button_height = 82
        left = (width - button_width) // 2
        top = height // 2 + 32
        self.ready_button = (left, top, left + button_width, top + button_height)
        cv.rectangle(self.canvas, self.ready_button[:2], self.ready_button[2:],
                     (40, 65, 55), -1, cv.LINE_AA)
        cv.rectangle(self.canvas, self.ready_button[:2], self.ready_button[2:],
                     (95, 220, 165), 3, cv.LINE_AA)
        label = "READY"
        label_size = cv.getTextSize(label, cv.FONT_HERSHEY_SIMPLEX, 0.9, 2)[0]
        cv.putText(self.canvas, label,
                   (center_x - label_size[0] // 2,
                    top + (button_height + label_size[1]) // 2),
                   cv.FONT_HERSHEY_SIMPLEX, 0.9, (245, 250, 240), 2, cv.LINE_AA)

    def ready_pressed(self, fingertips):
        if self.ready_button is None or len(fingertips) != 2:
            return False
        left, top, right, bottom = self.ready_button
        return all(left <= x <= right and top <= y <= bottom for x, y in fingertips)

    def begin_countdown(self, now=None):
        self.screen = "countdown"
        self.countdown_started = time.monotonic() if now is None else now

    def countdown_label(self, now=None):
        if self.countdown_started is None:
            return "READY"
        elapsed = (time.monotonic() if now is None else now) - self.countdown_started
        labels = ("READY", "STEADY", "GO")
        if elapsed >= len(labels):
            return None
        return labels[max(0, int(elapsed))]

    def draw_countdown(self, canvas, label):
        height, width = canvas.shape[:2]
        title = "WAVES MODE"
        title_size = cv.getTextSize(title, cv.FONT_HERSHEY_SIMPLEX, 0.65, 2)[0]
        cv.putText(canvas, title, ((width - title_size[0]) // 2, height // 2 - 80),
                   cv.FONT_HERSHEY_SIMPLEX, 0.65, (185, 210, 195), 2, cv.LINE_AA)
        label_size = cv.getTextSize(label, cv.FONT_HERSHEY_SIMPLEX, 1.8, 4)[0]
        cv.putText(canvas, label, ((width - label_size[0]) // 2, height // 2 + 20),
                   cv.FONT_HERSHEY_SIMPLEX, 1.8, (130, 235, 180), 4, cv.LINE_AA)

    def _draw_control_guide(self, height, width):
        title = "GAME CONTROLS"
        title_size = cv.getTextSize(title, cv.FONT_HERSHEY_SIMPLEX, 0.78, 2)[0]
        cv.putText(self.canvas, title, ((width - title_size[0]) // 2, 34),
                   cv.FONT_HERSHEY_SIMPLEX, 0.78, (235, 240, 245), 2, cv.LINE_AA)

        margin = 14
        gap = 10
        panel_width = (width - margin * 2 - gap) // 2
        panel_top = 52
        panel_bottom = height - 76
        left_panel = (margin, panel_top, margin + panel_width, panel_bottom)
        right_left = margin + panel_width + gap
        right_panel = (right_left, panel_top, right_left + panel_width, panel_bottom)
        for panel in (left_panel, right_panel):
            cv.rectangle(self.canvas, panel[:2], panel[2:], (39, 47, 48), -1)
            cv.rectangle(self.canvas, panel[:2], panel[2:], (68, 94, 85), 1)

        text_color = (220, 225, 214)
        accent = (113, 207, 171)
        cv.putText(self.canvas, "LEFT HAND: FIRE / RELOAD", (margin + 12, panel_top + 23),
                   cv.FONT_HERSHEY_SIMPLEX, 0.48, accent, 1, cv.LINE_AA)
        self._draw_hand_diagram(self.canvas,
                                (margin + panel_width // 3, panel_top + 87), "pinch", 0.52)
        self._draw_hand_diagram(self.canvas,
                                (margin + 2 * panel_width // 3, panel_top + 87), "thumb", 0.52)
        cv.putText(self.canvas, "PINCH: FIRE", (margin + 23, panel_top + 128),
                   cv.FONT_HERSHEY_SIMPLEX, 0.32, text_color, 1, cv.LINE_AA)
        cv.putText(self.canvas, "THUMB UP: RELOAD", (margin + panel_width // 2 + 8, panel_top + 128),
                   cv.FONT_HERSHEY_SIMPLEX, 0.32, text_color, 1, cv.LINE_AA)
        cv.line(self.canvas, (margin + 10, panel_top + 140),
                (margin + panel_width - 10, panel_top + 140), (68, 94, 85), 1, cv.LINE_AA)
        left_rows = (
            ("Pinch thumb + index to fire.", "Pistol: one shot per pinch."),
            ("Hold pinch for AK autofire.", "Thumb-up reloads selected gun."),
            ("Pistol: 8 rounds, higher damage.", "AK: 30 rounds, lower damage."),
        )
        y = panel_top + 163
        for first, second in left_rows:
            cv.putText(self.canvas, first, (margin + 12, y),
                       cv.FONT_HERSHEY_SIMPLEX, 0.37, text_color, 1, cv.LINE_AA)
            cv.putText(self.canvas, second, (margin + 12, y + 19),
                       cv.FONT_HERSHEY_SIMPLEX, 0.37, text_color, 1, cv.LINE_AA)
            y += 49
        cv.putText(self.canvas, "Aim with the RIGHT index cursor.",
               (margin + 12, panel_bottom - 12),
               cv.FONT_HERSHEY_SIMPLEX, 0.36, accent, 1, cv.LINE_AA)

        cv.putText(self.canvas, "RIGHT HAND: WEAPON", (right_left + 12, panel_top + 23),
                   cv.FONT_HERSHEY_SIMPLEX, 0.46, accent, 1, cv.LINE_AA)
        self._draw_hand_diagram(self.canvas,
                                (right_left + 51, panel_top + 84), "ok", 0.49)
        cv.putText(self.canvas, "OK sign = PISTOL", (right_left + 93, panel_top + 81),
                   cv.FONT_HERSHEY_SIMPLEX, 0.37, text_color, 1, cv.LINE_AA)
        self._draw_hand_diagram(self.canvas,
                                (right_left + 51, panel_top + 157), "ak", 0.49)
        cv.putText(self.canvas, "Index + middle up = AK", (right_left + 93, panel_top + 154),
                   cv.FONT_HERSHEY_SIMPLEX, 0.36, text_color, 1, cv.LINE_AA)
        cv.line(self.canvas, (right_left + 10, panel_top + 196),
                (right_left + panel_width - 10, panel_top + 196), (68, 94, 85), 1, cv.LINE_AA)
        right_rows = (
            "Curl ring + pinky for both poses.",
            "Weapon stays selected on release.",
            "R: reload    Q: quit",
            "Each zombie attack removes 12 health.",
        )
        y = panel_top + 222
        for row in right_rows:
            cv.putText(self.canvas, row, (right_left + 12, y),
                       cv.FONT_HERSHEY_SIMPLEX, 0.35, text_color, 1, cv.LINE_AA)
            y += 27

    @staticmethod
    def _draw_hand_diagram(canvas, center, pose, scale):
        center_x, center_y = center
        line_color = (184, 202, 191)
        joint_color = (110, 197, 158)

        def point(x, y):
            return (round(center_x + x * scale), round(center_y + y * scale))

        cv.ellipse(canvas, point(0, 9), (round(17 * scale), round(22 * scale)),
                   0, 0, 360, line_color, 2, cv.LINE_AA)
        cv.line(canvas, point(-9, 27), point(-9, 43), line_color, 3, cv.LINE_AA)
        cv.line(canvas, point(9, 27), point(9, 43), line_color, 3, cv.LINE_AA)
        cv.line(canvas, point(-9, 43), point(9, 43), line_color, 3, cv.LINE_AA)

        if pose == "pinch":
            finger_tips = [(-29, -5), (-10, -25), (0, -34), (10, -30), (19, -21)]
        elif pose == "thumb":
            finger_tips = [(-29, -31), (-14, 8), (-3, 12), (8, 14), (19, 16)]
        elif pose == "ok":
            finger_tips = [(-21, -18), (-19, -23), (-3, -39), (9, 5), (18, 9)]
        else:
            finger_tips = [(-21, -17), (-10, -42), (1, -46), (10, 5), (19, 9)]

        roots = [(-12, 4), (-10, -7), (-4, -10), (4, -7), (11, -2)]
        for root, tip in zip(roots, finger_tips):
            root_point = point(*root)
            tip_point = point(*tip)
            if pose == "pinch" and root == (-12, 4):
                middle_point = point(-27, -12)
                cv.line(canvas, root_point, middle_point, line_color, 3, cv.LINE_AA)
                cv.line(canvas, middle_point, tip_point, line_color, 3, cv.LINE_AA)
            else:
                bend = point((root[0] + tip[0]) / 2, (root[1] + tip[1]) / 2 - 3 * scale)
                cv.line(canvas, root_point, bend, line_color, 3, cv.LINE_AA)
                cv.line(canvas, bend, tip_point, line_color, 3, cv.LINE_AA)
            cv.circle(canvas, tip_point, max(2, round(3 * scale)), joint_color, -1, cv.LINE_AA)

    def _handle_mouse(self, event, x, y, flags, parameter):
        if event != cv.EVENT_LBUTTONDOWN:
            return

        panel_x = x if self.side == "left" else x - self.frame_width
        self.select_at((panel_x, y))

    def select_at(self, point):
        if point is None:
            return None

        x, y = point
        for (left, top, right, bottom), action in self.buttons:
            if left <= x <= right and top <= y <= bottom:
                if action in ("controls", "back", "play", "leaderboard", "try_again", "quit"):
                    if action == "back":
                        self.screen = "menu"
                    elif action == "play":
                        self.screen = "ready"
                    elif action == "try_again":
                        self.screen = "ready"
                    else:
                        self.screen = action
                self.action = action
                return action
        return None

    def _consume_action(self):
        action = self.action
        self.action = None
        return action