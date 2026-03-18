# drowsiness_detector.py
# Core drowsiness detection engine using MediaPipe + OpenCV

import cv2
import mediapipe as mp
import numpy as np
import threading
import time
import os
from utils import eye_aspect_ratio, mouth_aspect_ratio, compute_drowsiness_score

# ──────────────────────────────────────────────
# Thresholds & Constants
# ──────────────────────────────────────────────
EAR_THRESHOLD = 0.3         # EAR below this → eyes closing (lower = more sensitive)
MAR_THRESHOLD = 0.4         # MAR above this → mouth opening/yawning (lower = catches earlier)
EAR_CONSEC_FRAMES = 30      # Consecutive frames before declaring drowsy (~1 second at 30 FPS)
YAWN_CONSEC_FRAMES = 8      # Consecutive frames of open mouth before yawn alert

# MediaPipe face mesh indices for eyes and mouth
# References: https://github.com/google/mediapipe/blob/master/mediapipe/python/solutions/face_mesh_connections.py
LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_INDICES = [362, 387, 385, 263, 373, 380]
# Mouth landmarks: upper_lip, lower_lip, left_corner, right_corner
MOUTH_INDICES = [13, 14, 61, 291]


class DrowsinessDetector:
    """
    Real-time drowsiness detection using:
      - MediaPipe Face Mesh for facial landmarks
      - Eye Aspect Ratio (EAR) for eye closure detection
      - Mouth Aspect Ratio (MAR) for yawn detection
    """

    def __init__(self):
        # ── State flags ──
        self.is_running = False
        self.status = "Alert"           # "Alert" | "Drowsy" | "Yawning"
        self.ear_value = 0.0
        self.mar_value = 0.0
        self.score = 0                  # Drowsiness score 0–100
        self.frame_counter = 0          # Consecutive frames with closed eyes
        self.yawn_counter = 0           # Consecutive frames of open mouth
        self.alarm_triggered = False
        self.session_start = time.time()

        # ── Thread lock for shared state ──
        self.lock = threading.Lock()

        # ── MediaPipe Face Mesh ──
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # ── EAR history for score calculation ──
        self.ear_history = []

        # ── Video capture ──
        self.cap = None
        self.current_frame = None

        # ── Alarm ──
        self.alarm_thread = None
        self._init_alarm()

        # ── Load models ──
        self._load_models()

    # ──────────────────────────────────────────
    # Initialization helpers
    # ──────────────────────────────────────────

    def _init_alarm(self):
        """Initialize pygame mixer for alarm sound."""
        try:
            import pygame
            pygame.mixer.init()
            alarm_path = os.path.join(
                os.path.dirname(__file__), "..", "frontend", "assets", "alarm.wav"
            )
            if os.path.exists(alarm_path):
                pygame.mixer.music.load(alarm_path)
            self.pygame = pygame
            self.alarm_available = True
        except Exception as e:
            print(f"[WARN] Alarm init failed: {e}. Continuing without sound.")
            self.alarm_available = False

    def _load_models(self):
        """No models to load for MediaPipe."""
        pass

    # ──────────────────────────────────────────
    # Camera control
    # ──────────────────────────────────────────

    def start(self):
        """Open webcam and start detection loop in background thread."""
        if self.is_running:
            return

        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("[ERROR] Cannot access webcam (index 0).")

        self.is_running = True
        self.session_start = time.time()
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()
        print("[INFO] Detection started.")

    def stop(self):
        """Stop detection and release webcam."""
        self.is_running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self._stop_alarm()
        print("[INFO] Detection stopped.")

    # ──────────────────────────────────────────
    # Core detection loop
    # ──────────────────────────────────────────

    def _detection_loop(self):
        """
        Main loop: reads webcam frames, runs detection, annotates frame.
        Runs in a background thread.
        """
        while self.is_running:
            ret, frame = self.cap.read()
            if not ret:
                continue

            # Flip for mirror effect (more natural for driver)
            frame = cv2.flip(frame, 1)

            # Convert to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Detect faces and landmarks
            results = self.face_mesh.process(rgb_frame)

            new_status = "Alert"
            new_ear = 0.0
            new_mar = 0.0

            if results.multi_face_landmarks:
                # Process the first detected face
                landmarks = results.multi_face_landmarks[0]
                landmarks_array = np.array([(lm.x * frame.shape[1], lm.y * frame.shape[0]) for lm in landmarks.landmark])

                # ── Eye Aspect Ratio ──
                left_ear = eye_aspect_ratio(landmarks_array, LEFT_EYE_INDICES)
                right_ear = eye_aspect_ratio(landmarks_array, RIGHT_EYE_INDICES)
                avg_ear = (left_ear + right_ear) / 2.0
                new_ear = round(avg_ear, 3)

                # ── Mouth Aspect Ratio ──
                new_mar = round(mouth_aspect_ratio(landmarks_array, MOUTH_INDICES), 3)

                # ── Drowsiness logic ──
                with self.lock:
                    if avg_ear < EAR_THRESHOLD:
                        self.frame_counter += 1
                        if self.frame_counter >= EAR_CONSEC_FRAMES:
                            new_status = "Drowsy"
                            self._trigger_alarm()
                    else:
                        self.frame_counter = 0

                    if new_mar > MAR_THRESHOLD:
                        self.yawn_counter += 1
                        if self.yawn_counter >= YAWN_CONSEC_FRAMES:
                            if new_status == "Alert":
                                new_status = "Yawning"
                            self._trigger_alarm()
                    else:
                        self.yawn_counter = 0

                    if new_status == "Alert":
                        self._stop_alarm()

                    # Update EAR history and score
                    self.ear_history.append(avg_ear)
                    if len(self.ear_history) > 30:
                        self.ear_history.pop(0)
                    self.score = compute_drowsiness_score(avg_ear, new_mar, self.ear_history)

            else:
                # No face detected
                with self.lock:
                    self.frame_counter = 0
                    self.yawn_counter = 0
                    self._stop_alarm()
                    self.score = 0

            # Update status
            with self.lock:
                self.status = new_status
                self.ear_value = new_ear
                self.mar_value = new_mar

            # Store current frame for streaming
            self.current_frame = frame

            # ── Draw landmarks on frame ──
            if results.multi_face_landmarks:
                frame = self._draw_landmarks(frame, landmarks_array, avg_ear, new_mar, new_status)
            else:
                cv2.putText(frame, "No face detected", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

    # ──────────────────────────────────────────
    # Drawing helpers
    # ──────────────────────────────────────────

    def _draw_landmarks(self, frame, landmarks_array, ear, mar, status):
        """Draw eye and mouth landmarks, and status text on the frame."""
        # Draw eye landmarks
        eye_color = (0, 255, 0) if status == "Alert" else (0, 0, 255)
        for idx in LEFT_EYE_INDICES + RIGHT_EYE_INDICES:
            x, y = landmarks_array[idx]
            cv2.circle(frame, (int(x), int(y)), 2, eye_color, -1)

        # Draw mouth landmarks
        mouth_color = (0, 165, 255) if mar > MAR_THRESHOLD else (0, 255, 0)
        for idx in MOUTH_INDICES:
            x, y = landmarks_array[idx]
            cv2.circle(frame, (int(x), int(y)), 2, mouth_color, -1)

        # EAR / MAR values
        cv2.putText(frame, f"EAR: {ear:.2f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"MAR: {mar:.2f}", (10, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Status overlay
        if status == "Drowsy":
            cv2.putText(frame, "DROWSY!", (frame.shape[1]//2 - 80, frame.shape[0]//2),
                        cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 0, 255), 3)
        elif status == "Yawning":
            cv2.putText(frame, "YAWNING!", (frame.shape[1]//2 - 90, frame.shape[0]//2),
                        cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 165, 255), 3)

        return frame

    # ──────────────────────────────────────────
    # Alarm helpers
    # ──────────────────────────────────────────

    def _trigger_alarm(self):
        """Play alarm sound (non-blocking)."""
        if self.alarm_available and not self.alarm_triggered:
            self.alarm_triggered = True
            try:
                if not self.pygame.mixer.music.get_busy():
                    self.pygame.mixer.music.play(-1)  # loop
            except Exception:
                pass

    def _stop_alarm(self):
        """Stop alarm sound."""
        if self.alarm_available and self.alarm_triggered:
            self.alarm_triggered = False
            try:
                self.pygame.mixer.music.stop()
            except Exception:
                pass

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def get_status(self):
        """Return current detection state as a dict (thread-safe)."""
        with self.lock:
            elapsed = int(time.time() - self.session_start)
            return {
                "status": self.status,
                "ear": self.ear_value,
                "mar": self.mar_value,
                "score": self.score,
                "frame_count": self.frame_counter,
                "yawn_count": self.yawn_counter,
                "alarm": self.alarm_triggered,
                "session_seconds": elapsed,
                "is_running": self.is_running,
            }

    def get_frame(self):
        """Return the latest annotated frame as JPEG bytes (thread-safe)."""
        with self.lock:
            if self.current_frame is None:
                return None
            ret, jpeg = cv2.imencode(".jpg", self.current_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                return None
            return jpeg.tobytes()
