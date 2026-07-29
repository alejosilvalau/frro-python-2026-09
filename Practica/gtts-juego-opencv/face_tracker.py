import cv2
import mediapipe as mp
import numpy as np
import math


class FaceTracker:
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self.face_detected = False
        self.yaw = 0.0
        self.pitch = 0.0
        self.border_color = (0, 0, 255)
        self.frame = None

    def update(self):
        ret, frame = self.cap.read()
        if not ret:
            return

        frame = cv2.flip(frame, 1)
        self.frame = frame
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)

        if results.multi_face_landmarks:
            self.face_detected = True
            landmarks = results.multi_face_landmarks[0]
            h, w, _ = frame.shape

            nose_tip = landmarks.landmark[1]
            left_face = landmarks.landmark[234]
            right_face = landmarks.landmark[454]
            chin = landmarks.landmark[152]
            forehead = landmarks.landmark[10]

            nose_x = nose_tip.x * w
            face_center_x = (left_face.x + right_face.x) / 2 * w
            face_width = abs(right_face.x - left_face.x) * w
            if face_width > 0:
                self.yaw = (nose_x - face_center_x) / (face_width / 2)
                self.yaw = max(-1.0, min(1.0, self.yaw))
            else:
                self.yaw = 0.0

            nose_y = nose_tip.y * h
            face_center_y = (chin.y + forehead.y) / 2 * h
            face_height = abs(chin.y - forehead.y) * h
            if face_height > 0:
                self.pitch = (nose_y - face_center_y) / (face_height / 2)
                self.pitch = max(-1.0, min(1.0, self.pitch))
            else:
                self.pitch = 0.0
        else:
            self.face_detected = False
            self.yaw = 0.0
            self.pitch = 0.0

    def get_frame_with_border(self, key_fitted=False):
        if self.frame is None:
            return None

        frame = self.frame.copy()
        h, w = frame.shape[:2]

        if key_fitted:
            self.border_color = (0, 255, 255)
        elif self.face_detected:
            self.border_color = (0, 255, 0)
        else:
            self.border_color = (0, 0, 255)

        border = 8
        cv2.rectangle(frame, (0, 0), (w - 1, h - 1), self.border_color, border)

        label = "DETECTED" if self.face_detected else "NO FACE"
        cv2.putText(frame, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, self.border_color, 2)

        return frame

    def release(self):
        self.cap.release()
        self.face_mesh.close()
