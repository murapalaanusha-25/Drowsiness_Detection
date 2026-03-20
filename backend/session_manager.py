"""
session_manager.py — Handles session statistics, history, and data persistence
"""

import json
import time
from datetime import datetime
import csv
import os


class SessionManager:
    """Track drowsiness episodes, statistics, and session history."""

    def __init__(self):
        self.session_start_time = time.time()
        self.drowsy_episodes = []  # List of {start, end, duration}
        self.yawn_episodes = []    # List of {timestamp, intensity}
        self.alert_count = 0
        self.peak_drowsiness_score = 0
        self.total_drowsy_time = 0
        self.history_file = "session_history.json"
        self.load_history()

    def record_drowsy_episode(self, start_time, end_time, score):
        """Record a drowsiness episode."""
        duration = end_time - start_time
        self.drowsy_episodes.append({
            "start": start_time,
            "end": end_time,
            "duration": duration,
            "peak_score": score
        })
        self.total_drowsy_time += duration
        self.alert_count += 1
        self.peak_drowsiness_score = max(self.peak_drowsiness_score, score)

    def record_yawn(self, timestamp, intensity):
        """Record a yawn event."""
        self.yawn_episodes.append({
            "timestamp": timestamp,
            "intensity": intensity
        })

    def get_statistics(self):
        """Return session statistics as dict."""
        elapsed = time.time() - self.session_start_time
        return {
            "session_duration": int(elapsed),
            "drowsy_episodes": len(self.drowsy_episodes),
            "yawn_count": len(self.yawn_episodes),
            "alert_count": self.alert_count,
            "total_drowsy_time": int(self.total_drowsy_time),
            "peak_drowsiness_score": self.peak_drowsiness_score,
            "drowsy_percentage": round((self.total_drowsy_time / elapsed * 100), 2) if elapsed > 0 else 0
        }

    def export_csv(self, filename="session_data.csv"):
        """Export session data to CSV."""
        filepath = os.path.join("backend", filename)
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Episode Type", "Timestamp", "Duration (sec)", "Intensity/Score"])
            
            for ep in self.drowsy_episodes:
                writer.writerow(["Drowsiness", datetime.fromtimestamp(ep["start"]), ep["duration"], ep["peak_score"]])
            
            for yawn in self.yawn_episodes:
                writer.writerow(["Yawn", datetime.fromtimestamp(yawn["timestamp"]), "-", yawn["intensity"]])
        
        return filepath

    def save_session(self):
        """Save current session to history."""
        session_data = {
            "timestamp": datetime.now().isoformat(),
            "statistics": self.get_statistics(),
            "episodes": {
                "drowsy": self.drowsy_episodes,
                "yawns": self.yawn_episodes
            }
        }
        
        history = self.load_history()
        history.append(session_data)
        
        with open(self.history_file, 'w') as f:
            json.dump(history, f, indent=2)

    def load_history(self):
        """Load session history from file."""
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r') as f:
                return json.load(f)
        return []

    def get_history(self, limit=10):
        """Get recent sessions."""
        history = self.load_history()
        return history[-limit:]
