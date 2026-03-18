#!/bin/bash
# ─────────────────────────────────────────────────────────
# DrowsyGuard — Driver Drowsiness Detection System
# Run script: installs dependencies and starts the backend
# ─────────────────────────────────────────────────────────

set -e

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     DrowsyGuard — Drowsiness Detection       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Check Python ──
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed. Please install Python 3.8+"
    exit 1
fi

PYTHON_VER=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "[INFO] Python version: $PYTHON_VER"

# ── Check model file ──
MODEL_PATH="backend/models/shape_predictor_68_face_landmarks.dat"
if [ ! -f "$MODEL_PATH" ]; then
    echo ""
    echo "[ERROR] Model file not found: $MODEL_PATH"
    echo ""
    echo "Please download it:"
    echo "  1. Visit: https://github.com/davisking/dlib-models"
    echo "  2. Download: shape_predictor_68_face_landmarks.dat.bz2"
    echo "  3. Extract it: bunzip2 shape_predictor_68_face_landmarks.dat.bz2"
    echo "  4. Move to:   backend/models/"
    echo ""
    echo "Or run this command:"
    echo "  wget http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"
    echo "  bunzip2 shape_predictor_68_face_landmarks.dat.bz2"
    echo "  mv shape_predictor_68_face_landmarks.dat backend/models/"
    echo ""
    exit 1
fi

echo "[INFO] Model file found ✓"

# ── Create virtual environment if needed ──
if [ ! -d "venv" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv venv
fi

# ── Activate venv ──
source venv/bin/activate

# ── Install dependencies ──
echo "[INFO] Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r backend/requirements.txt

echo ""
echo "[INFO] Starting Flask backend..."
echo "[INFO] Open your browser at: http://localhost:5000"
echo "[INFO] Or open: frontend/index.html directly"
echo ""
echo "Press Ctrl+C to stop."
echo ""

# ── Start Flask ──
cd backend
python app.py
