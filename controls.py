
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

        for i, hand_landmarks in enumerate(
            results.multi_hand_landmarks
        ):
            hand = self.get_hand_side(results, i)

            if hand != "Left":
                continue

            landmarks = hand_landmarks.landmark

            index = landmarks[8].y < landmarks[6].y
            middle = landmarks[12].y < landmarks[10].y
            ring = landmarks[16].y < landmarks[14].y
            pinky = landmarks[20].y < landmarks[18].y

            return index and middle and ring and pinky

