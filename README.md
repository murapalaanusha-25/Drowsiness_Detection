# 🚗 DrowsyGuard — Driver Drowsiness Detection System

A real-time driver drowsiness detection system using Computer Vision and Machine Learning.
Detects eye closure and yawning via webcam and triggers audio + visual alerts.

---

## 📸 Features

- **Real-time webcam analysis** at ~30 FPS
- **Eye Aspect Ratio (EAR)** — detects eye closure
- **Mouth Aspect Ratio (MAR)** — detects yawning
- **Drowsiness Score** (0–100) combining EAR + MAR
- **Audio alarm** when drowsiness is detected
- **Live dashboard** — status indicator, gauges, ring chart, counters
- **Session timer** — tracks how long you've been driving
- **Zero cloud dependency** — runs fully locally

---

## 🧱 Tech Stack

| Layer     | Technology                                |
|-----------|-------------------------------------------|
| Backend   | Python 3, Flask, OpenCV, MediaPipe, NumPy, SciPy |
| Frontend  | HTML5, CSS3, Vanilla JavaScript           |
| Audio     | Pygame (server-side) + Web Audio API (browser-side) |
| ML Model  | MediaPipe Face Mesh (468-point facial landmarks) |

---

## 📁 Project Structure

```
driver-drowsiness-detection/
│
├── backend/
│   ├── app.py                   # Flask server & API routes
│   ├── drowsiness_detector.py   # Core detection engine
│   ├── utils.py                 # EAR / MAR / score calculations
│   ├── requirements.txt         # Python dependencies
│   ├── .env                     # Environment config (PORT=5000)
│   └── models/                  # (optional - placeholder)
│
├── frontend/
│   ├── index.html               # Dashboard UI
│   ├── style.css                # Dark HUD theme
│   ├── script.js                # API polling & UI updates
│   └── assets/
│       └── alarm.wav            # Alert sound
│
├── .gitignore
├── README.md
└── run.sh                       # One-click startup script
```

---

## ⬇️ Step 1: Download the Model File
Install Dependencies

### Requirements
- Python 3.8+
- A working webcam
- Linux / macOS / Windows

### Install
```bash
# Navigate to project root
cd driver-drowsiness-detection

# Create virtual environment
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r backend/requirements.txt
```

> **Note:** MediaPipe is included in requirements.txt and will be installed automatically. No additional compilation required!
---

## ▶️ Step 3: Run the System

### Option A — One-click script (Linux/Mac)
```bash
chmod +x run.sh
./run.sh
```

### Option B — Manual start
```bash
# Terminal 1: Start backend
cd backend
source ../venv/bin/activate
python app.py

# Then open frontend/index.html in your browser
```

---

## 🌐 Step 2: Run the System

### Option A — One-click script (Linux/Mac)
```bash
chmod +x run.sh
./run.sh
```

### Option B — Manual start
```bash
# Terminal 1: Start backend
cd backend
source ../venv/bin/activate      # Linux/Mac
venv\Scripts\activate            # Windows
python app.py

# Then open frontend/index.html in your browser
```

---

## 🌐 Step 3
---

## 🧠 How It Works

### Eye Aspect Ratio (EAR)
```
EAR = (||p2-p6|| + ||p3-p5||) / (2 × ||p1-p4||)
```
- Uses 6 eye landmarks from Dlib's 68-point model
- **EAR < 0.25 for 20+ consecutive frames → Drowsy**

### Mouth Aspect Ratio (MAR)
```
MAR = (A + B + C) / (2 × D)
```
- Uses 20 mouth landmarks
- **MAR > 0.60 for 10+ consecutive frames → Yawning**

### Drowsiness Score (0–100)
- **0–39:** Alert (green)
- **40–69:** Fatigued (amber)
- **70–100:** Drowsy/Critical (red)

---

## ⚠️ Troubleshooting

| Problem | Solution |MediaPipe Face Mesh
- *ModuleNotFoundError: No module named 'mediapipe'` | Run `pip install -r backend/requirements.txt` |
| `Cannot access webcam` | Check that no other app is using the webcam |
| CORS error in browser | Make sure Flask is running and CORS is enabled |
| No alarm sound | The browser Web Audio fallback will still beep |
| Detection not triggering | Adjust EAR_THRESHOLD (0.3) or MAR_THRESHOLD (0.4) in `drowsiness_detector.py`
```
- Uses 4 mouth landmarks from MediaPipe Face Mesh
- **MAR > 0.4 for 8+ consecutive frames (~0.25 sec)

## 🎓 College Project Notes

This project demonstrates:
- **Computer Vision** with OpenCV
- **Facial Landmark Detection** with MediaPipe Face Mesh
- **Signal Processing** (EAR/MAR threshold logic)
- **Real-time Streaming** with MJPEG over HTTP
- **Full-stack Web Development** with Flask + Vanilla JS
- **Zero-dependency ML** — No model downloads needed!

---

## 📄 License

MIT License — Free for educational use.
