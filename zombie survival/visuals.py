import cv2 as cv


class Visuals:
    def __init__(self):
        self.mouse_position = None

    def draw_mouse(self, canvas, results):
        self.mouse_position = None
        if not results or not results.multi_hand_landmarks or not results.multi_handedness:
            return None

        height, width = canvas.shape[:2]
        for hand_landmarks, handedness in zip(
            results.multi_hand_landmarks, results.multi_handedness
        ):
            if handedness.classification[0].label != "Right":
                continue

            index_tip = hand_landmarks.landmark[8]
            x = min(width - 1, max(0, round(index_tip.x * (width - 1))))
            y = min(height - 1, max(0, round(index_tip.y * (height - 1))))
            self.mouse_position = (x, y)

            cv.line(canvas, (x - 24, y), (x + 24, y), (80, 230, 170), 1, cv.LINE_AA)
            cv.line(canvas, (x, y - 24), (x, y + 24), (80, 230, 170), 1, cv.LINE_AA)
            cv.circle(canvas, self.mouse_position, 18, (80, 230, 170), 2, cv.LINE_AA)
            cv.circle(canvas, self.mouse_position, 4, (255, 255, 255), -1, cv.LINE_AA)
            return self.mouse_position

        return None