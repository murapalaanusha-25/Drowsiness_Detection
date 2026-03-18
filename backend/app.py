# app.py
# Flask backend for Driver Drowsiness Detection System

import os
from flask import Flask, Response, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from drowsiness_detector import DrowsinessDetector

# ── Load environment variables ──
load_dotenv()

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from frontend

# ── Global detector instance ──
detector = DrowsinessDetector()


# ──────────────────────────────────────────────
# Helper: MJPEG frame generator
# ──────────────────────────────────────────────

def generate_frames():
    """
    Generator function that yields MJPEG frames for the /video_feed endpoint.
    Each frame is encoded as JPEG and wrapped in multipart HTTP response.
    """
    import time
    while True:
        if not detector.is_running:
            # Send a blank placeholder frame when camera is off
            import cv2
            import numpy as np
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(blank, "Camera Off", (220, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (100, 100, 100), 2)
            _, jpeg = cv2.imencode(".jpg", blank)
            frame_bytes = jpeg.tobytes()
        else:
            frame_bytes = detector.get_frame()
            if frame_bytes is None:
                time.sleep(0.03)
                continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame_bytes +
            b"\r\n"
        )
        time.sleep(0.03)  # ~30 FPS cap


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the frontend index.html"""
    return send_from_directory("../frontend", "index.html")

@app.route("/<path:path>")
def static_files(path):
    """Serve static files from frontend directory"""
    return send_from_directory("../frontend", path)

@app.route("/video_feed")
def video_feed():
    """
    MJPEG video stream endpoint.
    Use as <img src="http://localhost:5000/video_feed"> in HTML.
    """
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/status")
def status():
    """
    Returns current drowsiness detection state as JSON.
    Called by frontend every second to update UI.
    """
    return jsonify(detector.get_status())


@app.route("/start", methods=["POST"])
def start_camera():
    """Start the webcam and detection loop."""
    try:
        if not detector.is_running:
            detector.start()
        return jsonify({"success": True, "message": "Detection started"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/stop", methods=["POST"])
def stop_camera():
    """Stop the webcam and detection loop."""
    try:
        detector.stop()
        return jsonify({"success": True, "message": "Detection stopped"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "model_loaded": True})


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"\n🚗 Driver Drowsiness Detection Server")
    print(f"   Running at: http://localhost:{port}")
    print(f"   Video feed: http://localhost:{port}/video_feed")
    print(f"   Status API: http://localhost:{port}/status\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
