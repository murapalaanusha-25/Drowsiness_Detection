# drowsiness_detector.py
# Core drowsiness detection engine using MediaPipe + OpenCV

import cv2
import mediapipe as mp
import numpy as np
import threading
import time
import os
from utils import eye_aspect_ratio, mouth_aspect_ratio, compute_drowsiness_score
from session_manager import SessionManager
from risk_assessment import RiskAssessment

# ──────────────────────────────────────────────
# Thresholds & Constants
# ──────────────────────────────────────────────
EAR_THRESHOLD = 0.3         # EAR below this → eyes closing (lower = more sensitive)
MAR_THRESHOLD = 0.4         # MAR above this → mouth opening/yawning (lower = catches earlier)
EAR_CONSEC_FRAMES = 30      # Consecutive frames before declaring drowsy (~1 second at 30 FPS)
YAWN_CONSEC_FRAMES = 8      # Consecutive frames of open mouth before yawn alert
MAX_FACES = 1               # Single face detection for focused monitoring

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

        # -- Dynamic thresholds (can be adjusted via API) --
        self.ear_threshold = EAR_THRESHOLD
        self.mar_threshold = MAR_THRESHOLD
        self.ear_consec_frames = EAR_CONSEC_FRAMES
        self.yawn_consec_frames = YAWN_CONSEC_FRAMES

        # ── Threading and state management ──
        self.lock = threading.Lock()
        
        # ── Advanced features ──
        self.session_manager = SessionManager()
        self.risk_assessment = RiskAssessment()
        self.multi_face_data = {}  # {face_id: detector_state}
        self.frame_times = []  # For FPS calculation
        self.processing_times = []  # For latency metrics

        # ── MediaPipe Face Mesh (multi-face support) ──
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=MAX_FACES,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # ── EAR history for score calculation ──
        self.ear_history = []

        # ── Video capture ──
        self.cap = None
        self.current_frame = None

        # ── Performance metrics ──
        self.fps = 0
        self.latency_ms = 0
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
    def _enhance_low_light(self, frame, brightness_threshold=50, clip_limit=3.0, tile_grid_size=(8, 8)):
        """Apply automatic contrast/brightness correction to help in low-light scenes.

        This function performs a quick brightness check and, if the frame is dark,
        applies CLAHE on the L channel (Lab color space) plus a gentle gamma boost.
        """
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if np.mean(gray) < brightness_threshold:
                # Enhance contrast via CLAHE on the L channel
                lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
                l = clahe.apply(l)
                enhanced = cv2.merge((l, a, b))
                frame = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

                # Smooth gamma correction to brighten shadows
                gamma = 1.2  # reduced from 1.4 for more natural look
                inv_gamma = 1.0 / gamma
                table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(256)]).astype("uint8")
                frame = cv2.LUT(frame, table)

                # Additional brightness boost for very dark scenes
                if np.mean(gray) < 30:
                    frame = cv2.convertScaleAbs(frame, alpha=1.2, beta=20)
        except Exception:
            # If enhancement fails (some cameras may not like conversions), keep original frame
            pass

        return frame
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
        Runs in a background thread. Supports multi-face detection and performance metrics.
        """
        frame_time_prev = time.time()
        
        while self.is_running:
            frame_time_start = time.time()
            ret, frame = self.cap.read()
            if not ret:
                continue

            # Flip for mirror effect (more natural for driver)
            frame = cv2.flip(frame, 1)

            # Improve visibility in low-light conditions (dark cabins)
            frame = self._enhance_low_light(frame)

            # Convert to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Detect faces and landmarks
            results = self.face_mesh.process(rgb_frame)

            new_status = "Alert"
            new_ear = 0.0
            new_mar = 0.0
            face_count = 0

            if results.multi_face_landmarks:
                ear_values = []
                mar_values = []
                statuses = []

                for face_idx, landmarks in enumerate(results.multi_face_landmarks):
                    landmarks_array = np.array([(lm.x * frame.shape[1], lm.y * frame.shape[0]) for lm in landmarks.landmark])

                    # ── Eye Aspect Ratio ──
                    left_ear = eye_aspect_ratio(landmarks_array, LEFT_EYE_INDICES)
                    right_ear = eye_aspect_ratio(landmarks_array, RIGHT_EYE_INDICES)
                    avg_ear = (left_ear + right_ear) / 2.0
                    ear_values.append(avg_ear)

                    # ── Mouth Aspect Ratio ──
                    mar = mouth_aspect_ratio(landmarks_array, MOUTH_INDICES)
                    mar_values.append(mar)

                    # ── Calibration mode recording ──
                    if self.risk_assessment.is_calibrating:
                        self.risk_assessment.record_calibration_frame(avg_ear, mar)

                    # ── Drowsiness logic for this face ──
                    face_status = "Alert"
                    with self.lock:
                        # Use dynamic thresholds
                        if avg_ear < self.ear_threshold:
                            self.frame_counter += 1
                            if self.frame_counter >= self.ear_consec_frames:
                                face_status = "Drowsy"
                        else:
                            self.frame_counter = 0

                        if mar > self.mar_threshold:
                            self.yawn_counter += 1
                            if self.yawn_counter >= self.yawn_consec_frames:
                                if face_status == "Alert":
                                    face_status = "Yawning"
                        else:
                            self.yawn_counter = 0

                    statuses.append(face_status)

                    # Draw landmarks for this face
                    frame = self._draw_landmarks(frame, landmarks_array, avg_ear, mar, face_status)

                # ── Aggregate results across all faces ──
                # Overall status: Drowsy if any face is drowsy, Yawning if any is yawning but none drowsy, else Alert
                if "Drowsy" in statuses:
                    new_status = "Drowsy"
                    self._trigger_alarm()
                elif "Yawning" in statuses:
                    new_status = "Yawning"
                    self._trigger_alarm()
                else:
                    new_status = "Alert"
                    self._stop_alarm()

                # Average EAR and MAR across all faces
                new_ear = round(np.mean(ear_values), 3)
                new_mar = round(np.mean(mar_values), 3)

                # Update EAR history and score using averages
                self.ear_history.append(new_ear)
                if len(self.ear_history) > 30:
                    self.ear_history.pop(0)
                self.score = compute_drowsiness_score(new_ear, new_mar, self.ear_history, 
                                                     self.ear_threshold, self.mar_threshold)

                face_count = len(results.multi_face_landmarks)

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

            # ── Draw face count ──
            if face_count > 0:
                cv2.putText(frame, f"Faces: {face_count}", (10, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            else:
                cv2.putText(frame, "No face detected", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

            # ── Performance metrics ──
            frame_time_elapsed = time.time() - frame_time_start
            frame_time_current = time.time()
            self._calculate_metrics(frame_time_current, frame_time_elapsed)
            frame_time_prev = frame_time_current

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
    # Advanced Features: Calibration, Risk Assessment
    # ──────────────────────────────────────────

    def start_calibration(self):
        """Start calibration mode."""
        self.risk_assessment.start_calibration()
        return {"message": "Calibration started. Keep eyes open and face camera normally."}

    def end_calibration(self):
        """End calibration and compute baselines."""
        success = self.risk_assessment.end_calibration()
        if success:
            return {"message": "Calibration complete!", "baseline": {
                "ear": self.risk_assessment.ear_baseline,
                "mar": self.risk_assessment.mar_baseline
            }}
        return {"message": "Not enough calibration data. Try again.", "success": False}

    def update_thresholds(self, ear_threshold=None, mar_threshold=None):
        """Dynamically adjust detection thresholds from frontend."""
        with self.lock:
            if ear_threshold is not None:
                self.ear_threshold = ear_threshold
            if mar_threshold is not None:
                self.mar_threshold = mar_threshold
        return {
            "ear_threshold": self.ear_threshold,
            "mar_threshold": self.mar_threshold
        }

    def get_performance_metrics(self):
        """Return FPS and latency metrics."""
        with self.lock:
            return {
                "fps": round(self.fps, 2),
                "latency_ms": round(self.latency_ms, 2),
                "detect_quality": "Good" if self.fps > 25 else "Low FPS"
            }

    def _calculate_metrics(self, frame_time, process_time):
        """Update FPS and latency calculations."""
        self.frame_times.append(frame_time)
        self.processing_times.append(process_time)
        
        if len(self.frame_times) > 30:
            self.frame_times.pop(0)
        if len(self.processing_times) > 30:
            self.processing_times.pop(0)
        
        if len(self.frame_times) > 1:
            self.fps = 1.0 / np.mean(np.diff(self.frame_times))
            self.latency_ms = np.mean(self.processing_times) * 1000

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def get_status(self):
        """Return current detection state as a dict (thread-safe)."""
        with self.lock:
            elapsed = time.time() - self.session_start
            stats = self.session_manager.get_statistics()
            risk = self.risk_assessment.get_risk_level(self.score)
            break_suggestion = self.risk_assessment.suggest_break(stats["total_drowsy_time"], elapsed)
            
            return {
                "status": self.status,
                "ear": self.ear_value,
                "mar": self.mar_value,
                "score": self.score,
                "risk_level": risk,
                "frame_count": self.frame_counter,
                "yawn_count": self.yawn_counter,
                "alarm": self.alarm_triggered,
                "session_seconds": int(elapsed),
                "is_running": self.is_running,
                "statistics": stats,
                "break_suggestion": break_suggestion,
                "calibration_mode": self.risk_assessment.is_calibrating,
                "fps": round(self.fps, 1),
                "latency_ms": round(self.latency_ms, 1),
                "current_thresholds": {
                    "ear": self.ear_threshold,
                    "mar": self.mar_threshold
                }
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
