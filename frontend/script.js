/**
 * script.js
 * DrowsyGuard frontend — handles:
 *   - Camera start/stop via Flask API
 *   - Polling /status every 800ms for live updates
 *   - Updating UI: status card, EAR/MAR gauges, score ring, counters
 *   - Triggering alert popup + browser audio fallback
 *   - Session timer
 */

// ──────────────────────────────────────────────
// Config
// ──────────────────────────────────────────────
const API_BASE = "http://localhost:5000";
const POLL_INTERVAL_MS = 800;

// ──────────────────────────────────────────────
// State
// ──────────────────────────────────────────────
let pollTimer = null;
let sessionInterval = null;
let sessionSeconds = 0;
let alertShown = false;
let lastStatus = "idle";

// Browser AudioContext for alarm fallback
let audioCtx = null;
let alarmPlaying = false;

// ──────────────────────────────────────────────
// DOM references
// ──────────────────────────────────────────────
const videoStream     = document.getElementById("videoStream");
const videoOverlay    = document.getElementById("videoOverlay");
const overlayStatus   = document.getElementById("overlayStatus");
const videoContainer  = document.getElementById("videoContainer");

const startBtn        = document.getElementById("startBtn");
const stopBtn         = document.getElementById("stopBtn");

const statusCard      = document.getElementById("statusCard");
const statusDot       = document.getElementById("statusDot");
const statusText      = document.getElementById("statusText");
const statusSub       = document.getElementById("statusSub");

const earValue        = document.getElementById("earValue");
const earFill         = document.getElementById("earFill");
const marValue        = document.getElementById("marValue");
const marFill         = document.getElementById("marFill");

const ringFill        = document.getElementById("ringFill");
const scoreNumber     = document.getElementById("scoreNumber");
const scoreSub        = document.getElementById("scoreSub");

const frameCount      = document.getElementById("frameCount");
const yawnCount       = document.getElementById("yawnCount");

const timerDisplay    = document.getElementById("timerDisplay");
const connIndicator   = document.getElementById("connIndicator");
const connText        = connIndicator.querySelector(".conn-text");

const alertPopup      = document.getElementById("alertPopup");
const alertBackdrop   = document.getElementById("alertBackdrop");
const alertIcon       = document.getElementById("alertIcon");
const alertTitle      = document.getElementById("alertTitle");
const alertMsg        = document.getElementById("alertMsg");


// ──────────────────────────────────────────────
// Camera controls
// ──────────────────────────────────────────────

async function startCamera() {
  try {
    const res = await fetch(`${API_BASE}/start`, { method: "POST" });
    const data = await res.json();

    if (data.success) {
      // Show video stream
      videoStream.src = `${API_BASE}/video_feed`;
      videoOverlay.classList.add("hidden");

      startBtn.disabled = true;
      stopBtn.disabled = false;

      // Start session timer
      sessionSeconds = 0;
      if (sessionInterval) clearInterval(sessionInterval);
      sessionInterval = setInterval(tickTimer, 1000);

      // Start polling
      startPolling();

      setConnection("connected");
    } else {
      alert("Failed to start: " + data.message);
    }
  } catch (err) {
    console.error("Start error:", err);
    alert("Cannot connect to backend.\nMake sure the Flask server is running on port 5000.");
    setConnection("error");
  }
}

async function stopCamera() {
  try {
    await fetch(`${API_BASE}/stop`, { method: "POST" });
  } catch (e) {
    console.warn("Stop request failed:", e);
  }

  // Reset UI
  videoStream.src = "";
  videoOverlay.classList.remove("hidden");
  overlayStatus.textContent = "CAMERA OFF";

  startBtn.disabled = false;
  stopBtn.disabled = true;

  stopPolling();
  if (sessionInterval) clearInterval(sessionInterval);
  stopAlarm();
  resetDashboard();
  setConnection("idle");
}

// ──────────────────────────────────────────────
// Status polling
// ──────────────────────────────────────────────

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(fetchStatus, POLL_INTERVAL_MS);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function fetchStatus() {
  try {
    const res = await fetch(`${API_BASE}/status`);
    if (!res.ok) throw new Error("Bad response");
    const data = await res.json();
    updateDashboard(data);
    setConnection("connected");
  } catch (err) {
    console.warn("Poll error:", err);
    setConnection("error");
  }
}

// ──────────────────────────────────────────────
// Dashboard update
// ──────────────────────────────────────────────

function updateDashboard(data) {
  const status  = data.status || "Alert";
  const ear     = data.ear || 0;
  const mar     = data.mar || 0;
  const score   = data.score || 0;

  // ── Status card ──
  const statusClass = status.toLowerCase();

  statusCard.className = `status-card state-${statusClass}`;
  statusDot.className  = `status-dot ${statusClass}`;
  statusText.className = `status-text ${statusClass}`;
  statusText.textContent = status.toUpperCase();

  const subMessages = {
    alert:   "All systems normal",
    drowsy:  "⚠ Eyes closing detected!",
    yawning: "Fatigue yawn detected",
  };
  statusSub.textContent = subMessages[statusClass] || "Monitoring…";

  // ── EAR gauge ──
  earValue.textContent = ear.toFixed(3);
  // EAR range: 0 – 0.45 (0 = fully closed, 0.45 = wide open)
  const earPct = Math.min(100, (ear / 0.45) * 100);
  earFill.style.width = earPct + "%";
  earFill.style.background = ear < 0.25
    ? "linear-gradient(90deg, #ff1744, #ff4060)"
    : "linear-gradient(90deg, #00e676, #00bfff)";

  // ── MAR gauge ──
  marValue.textContent = mar.toFixed(3);
  // MAR range: 0 – 1.2
  const marPct = Math.min(100, (mar / 1.2) * 100);
  marFill.style.width = marPct + "%";
  marFill.style.background = mar > 0.6
    ? "linear-gradient(90deg, #ff9100, #ff1744)"
    : "linear-gradient(90deg, #00bfff, #00e676)";

  // ── Score ring ──
  // Ring circumference = 2π × r = 2π × 50 ≈ 314
  const circumference = 314;
  const offset = circumference - (score / 100) * circumference;
  ringFill.style.strokeDashoffset = offset;

  // Ring color by score
  ringFill.className = "ring-fill";
  if (score >= 70) ringFill.classList.add("danger");
  else if (score >= 40) ringFill.classList.add("warning");

  scoreNumber.textContent = score;
  const scoreLabels = score < 30 ? "Fully alert" : score < 60 ? "Getting tired" : score < 80 ? "Very fatigued" : "CRITICAL";
  scoreSub.textContent = scoreLabels;

  // ── Counters ──
  frameCount.textContent = data.frame_count || 0;
  yawnCount.textContent  = data.yawn_count  || 0;

  // ── Session timer from server ──
  if (data.session_seconds) {
    sessionSeconds = data.session_seconds;
    updateTimerDisplay(sessionSeconds);
  }

  // ── Video container border ──
  if (status === "Drowsy" || status === "Yawning") {
    videoContainer.classList.add("alert-active");
  } else {
    videoContainer.classList.remove("alert-active");
  }

  // ── Trigger alert popup & alarm ──
  if ((status === "Drowsy" || status === "Yawning") && !alertShown) {
    triggerAlert(status);
    playAlarm();
  } else if (status === "Alert") {
    alertShown = false;
    stopAlarm();
  }

  lastStatus = status;
}

function resetDashboard() {
  statusCard.className = "status-card";
  statusDot.className  = "status-dot";
  statusText.className = "status-text";
  statusText.textContent = "—";
  statusSub.textContent = "System Idle";

  earValue.textContent = "—";
  earFill.style.width  = "0%";
  marValue.textContent = "—";
  marFill.style.width  = "0%";

  ringFill.style.strokeDashoffset = "314";
  ringFill.className = "ring-fill";
  scoreNumber.textContent = "0";
  scoreSub.textContent = "No data";

  frameCount.textContent = "0";
  yawnCount.textContent  = "0";
  videoContainer.classList.remove("alert-active");
}

// ──────────────────────────────────────────────
// Alert popup
// ──────────────────────────────────────────────

function triggerAlert(status) {
  alertShown = true;

  if (status === "Drowsy") {
    alertIcon.textContent = "😴";
    alertTitle.textContent = "DROWSINESS DETECTED";
    alertMsg.textContent = "Your eyes have been closed for too long. Please pull over safely and rest.";
  } else {
    alertIcon.textContent = "🥱";
    alertTitle.textContent = "YAWNING DETECTED";
    alertMsg.textContent = "Repeated yawning indicates fatigue. Consider taking a break soon.";
  }

  alertPopup.classList.add("visible");
  alertBackdrop.classList.add("visible");
}

function dismissAlert() {
  alertPopup.classList.remove("visible");
  alertBackdrop.classList.remove("visible");
  stopAlarm();
}

// ──────────────────────────────────────────────
// Browser-side alarm (fallback using Web Audio)
// ──────────────────────────────────────────────

function playAlarm() {
  if (alarmPlaying) return;
  alarmPlaying = true;

  try {
    // Try loading the WAV file first
    const audio = new Audio("assets/alarm.wav");
    audio.loop = true;
    audio.play().catch(() => playBeep()); // Fallback to beep
    window._alarmAudio = audio;
  } catch (e) {
    playBeep();
  }
}

function playBeep() {
  // Web Audio API beep as ultimate fallback
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }

  function beep() {
    if (!alarmPlaying) return;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.frequency.value = 880;
    osc.type = "square";
    gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.3);
    osc.start(audioCtx.currentTime);
    osc.stop(audioCtx.currentTime + 0.3);
    setTimeout(beep, 600);
  }
  beep();
}

function stopAlarm() {
  alarmPlaying = false;
  if (window._alarmAudio) {
    window._alarmAudio.pause();
    window._alarmAudio.currentTime = 0;
    window._alarmAudio = null;
  }
}

// ──────────────────────────────────────────────
// Session timer
// ──────────────────────────────────────────────

function tickTimer() {
  sessionSeconds++;
  updateTimerDisplay(sessionSeconds);
}

function updateTimerDisplay(secs) {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  timerDisplay.textContent = [h, m, s].map(v => String(v).padStart(2, "0")).join(":");
}

// ──────────────────────────────────────────────
// Connection indicator
// ──────────────────────────────────────────────

function setConnection(state) {
  connIndicator.className = "conn-indicator";
  if (state === "connected") {
    connIndicator.classList.add("connected");
    connText.textContent = "CONNECTED";
  } else if (state === "error") {
    connIndicator.classList.add("error");
    connText.textContent = "ERROR";
  } else {
    connText.textContent = "IDLE";
  }
}

// ──────────────────────────────────────────────
// Initial connection check
// ──────────────────────────────────────────────

async function checkBackend() {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    if (res.ok) {
      setConnection("connected");
      connText.textContent = "READY";
    }
  } catch {
    setConnection("error");
    console.warn("Backend not reachable. Start Flask server first.");
  }
}

// Run health check on page load
checkBackend();
