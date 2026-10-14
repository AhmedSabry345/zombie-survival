
class Control:
    def __init__(self):
        pass

    def get_hand_side(self, results, hand_index=0):

        if not results.multi_hand_landmarks:
            return None

        if hand_index >= len(results.multi_hand_landmarks):
            return None

        return results.multi_handedness[
            hand_index
        ].classification[0].label

    def left_hand_open(self, results):

        if not results.multi_hand_landmarks:
            return False

        for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
            hand = self.get_hand_side(results, i)

            if hand != "Left":
                continue

            landmarks = hand_landmarks.landmark

            index = landmarks[8].y < landmarks[6].y
            middle = landmarks[12].y < landmarks[10].y
            ring = landmarks[16].y < landmarks[14].y
            pinky = landmarks[20].y < landmarks[18].y

            return index and middle and ring and pinky

    def left_hand_reload(self, results):
        if not results.multi_hand_landmarks:
            return False

        for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
            if self.get_hand_side(results, i) != "Left":
                continue

            landmarks = hand_landmarks.landmark
            thumb_up = landmarks[4].y < landmarks[3].y
            fingers_curled = all(
                landmarks[tip].y > landmarks[pip].y
                for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18))
            )
            return thumb_up and fingers_curled

        return False

    def both_index_fingertips(self, results, canvas_shape):
        if not results.multi_hand_landmarks or not results.multi_handedness:
            return []

        height, width = canvas_shape[:2]
        fingertips = []
        for hand_landmarks in results.multi_hand_landmarks:
            landmarks = hand_landmarks.landmark
            if landmarks[8].y >= landmarks[6].y:
                continue
            x = min(width - 1, max(0, round(landmarks[8].x * (width - 1))))
            y = min(height - 1, max(0, round(landmarks[8].y * (height - 1))))
            fingertips.append((x, y))

        return fingertips if len(fingertips) == 2 else []



    def shooting(self, results, hand_side="Left"):
        if not results.multi_hand_landmarks:
            return False

        for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
            hand = self.get_hand_side(results, i)

            if hand != hand_side:
                continue

            landmarks = hand_landmarks.landmark
            thumb = landmarks[4]
            index_tip = landmarks[8]

            dist = ((thumb.x - index_tip.x) ** 2 + (thumb.y - index_tip.y) ** 2) ** 0.5

            return dist < 0.05

        return False

    
    def gun_type(self, results, hand_side="Right"):

        if not results.multi_hand_landmarks:
            return False

        for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
            hand = self.get_hand_side(results, i)

            if hand != hand_side:
                continue

            landmarks = hand_landmarks.landmark

            ring = landmarks[16].y > landmarks[14].y
            pinky = landmarks[20].y > landmarks[18].y
            middle_up = landmarks[12].y < landmarks[10].y
            index_up = landmarks[8].y < landmarks[6].y
            thumb_up = landmarks[4].y < landmarks[3].y
            middle_curled = landmarks[12].y > landmarks[10].y
            index_curled = landmarks[8].y > landmarks[6].y
            thumb_index_touch = (
                (landmarks[4].x - landmarks[8].x) ** 2
                + (landmarks[4].y - landmarks[8].y) ** 2
            ) ** 0.5 < 0.05
            ok_sign = (
                thumb_index_touch
                and middle_up
                and not ring
                and not pinky
            )

            if ring and pinky and middle_up and index_up:
                return 2
            elif ok_sign:
                return 1
            elif thumb_up and index_curled and middle_curled and ring and pinky:
                return 1
        