"""
risk_assessment.py — Risk scoring and calibration system
"""

import numpy as np


class RiskAssessment:
    """Calculate risk level based on drowsiness patterns."""

    RISK_LEVELS = {
        "LOW": {"range": (0, 40), "color": "#00FF00", "label": "Alert"},
        "MEDIUM": {"range": (40, 70), "color": "#FFA500", "label": "Fatigued"},
        "HIGH": {"range": (70, 100), "color": "#FF0000", "label": "Critical"}
    }

    def __init__(self):
        self.ear_baseline = None
        self.mar_baseline = None
        self.calibration_data = []
        self.is_calibrating = False

    def start_calibration(self):
        """Start calibration mode - user keeps eyes open and normal."""
        self.is_calibrating = True
        self.calibration_data = []

    def record_calibration_frame(self, ear, mar):
        """Record EAR and MAR values during calibration."""
        if self.is_calibrating:
            self.calibration_data.append({"ear": ear, "mar": mar})

    def end_calibration(self):
        """Compute baseline from calibration data."""
        if len(self.calibration_data) < 10:
            return False
        
        ears = [d["ear"] for d in self.calibration_data]
        mars = [d["mar"] for d in self.calibration_data]
        
        self.ear_baseline = {
            "mean": np.mean(ears),
            "std": np.std(ears)
        }
        self.mar_baseline = {
            "mean": np.mean(mars),
            "std": np.std(mars)
        }
        
        self.is_calibrating = False
        return True

    def get_risk_level(self, score):
        """Return risk level based on drowsiness score."""
        for level, data in self.RISK_LEVELS.items():
            if data["range"][0] <= score < data["range"][1]:
                return {"level": level, "score": score, **data}
        return {"level": "HIGH", "score": 100, **self.RISK_LEVELS["HIGH"]}

    def get_escalation_factor(self, consecutive_episodes):
        """Get alert escalation based on repeated episodes."""
        if consecutive_episodes == 0:
            return 1.0
        elif consecutive_episodes == 1:
            return 1.2
        elif consecutive_episodes == 2:
            return 1.5
        else:
            return 2.0  # Critical escalation after 3+ episodes

    def suggest_break(self, total_drowsy_time, session_duration):
        """Suggest break based on drowsiness pattern."""
        drowsy_percentage = (total_drowsy_time / session_duration * 100) if session_duration > 0 else 0
        
        if drowsy_percentage > 30:
            return {
                "recommend_break": True,
                "urgency": "Critical",
                "message": "⚠️ CRITICAL: You've been drowsy for >30% of the session. Take a break immediately!"
            }
        elif drowsy_percentage > 20:
            return {
                "recommend_break": True,
                "urgency": "High",
                "message": "⚠️ HIGH: You've been drowsy for >20% of session. Consider taking a break soon."
            }
        elif drowsy_percentage > 10:
            return {
                "recommend_break": True,
                "urgency": "Medium",
                "message": "Take a short break to refresh."
            }
        else:
            return {"recommend_break": False, "urgency": "Low", "message": "You're doing well!"}
