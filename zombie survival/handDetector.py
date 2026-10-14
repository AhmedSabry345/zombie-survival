import mediapipe as mp
import cv2 as cv
from controls import Control

ctr = Control()
class handDetector:
    def __init__(self, max_hand = 2):
        self.max_hand = max_hand
        self.mpHands = mp.solutions.hands
        self.Hands = self.mpHands.Hands(max_num_hands = self.max_hand)
        self.painter = mp.solutions.drawing_utils


    def detect_hands(self, frame):
        frameRGB = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
        results = self.Hands.process(frameRGB)
        if results.multi_hand_landmarks:
            for handlms in results.multi_hand_landmarks:
                self.painter.draw_landmarks(frame, handlms, self.mpHands.HAND_CONNECTIONS)
        return results

