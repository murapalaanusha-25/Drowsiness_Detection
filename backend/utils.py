"""
utils.py — Helper functions for Eye Aspect Ratio (EAR) and Mouth Aspect Ratio (MAR)
These are the core mathematical formulas used in drowsiness detection.
"""

from scipy.spatial import distance as dist
import numpy as np


def eye_aspect_ratio(landmarks, eye_indices):
    """
    Calculate the Eye Aspect Ratio (EAR) for a single eye.

    Parameters:
        landmarks: numpy array of shape (n, 2) with (x, y) coordinates
        eye_indices: list of 6 indices for the eye landmarks

    Returns:
        float: EAR value
    """
    eye = landmarks[eye_indices]
    # Vertical distances
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    # Horizontal distance
    C = dist.euclidean(eye[0], eye[3])
    ear = (A + B) / (2.0 * C)
    return ear


def mouth_aspect_ratio(landmarks, mouth_indices):
    """Calculate the Mouth Aspect Ratio (MAR) for yawn detection.

    Uses MediaPipe FaceMesh landmarks by default.

    Parameters:
        landmarks: numpy array of shape (n, 2) with (x, y) coordinates
        mouth_indices: list of 4 indices for the mouth landmarks in the
            order: [upper_lip, lower_lip, left_corner, right_corner]

    Returns:
        float: MAR value (vertical / horizontal ratio)
    """
    if len(mouth_indices) < 4:
        return 0.0

    upper = landmarks[mouth_indices[0]]
    lower = landmarks[mouth_indices[1]]
    left = landmarks[mouth_indices[2]]
    right = landmarks[mouth_indices[3]]

    vertical = dist.euclidean(upper, lower)
    horizontal = dist.euclidean(left, right)

    if horizontal == 0:
        return 0.0

    return vertical / horizontal


def compute_drowsiness_score(ear, mar, ear_history, ear_thresh=0.3, mar_thresh=0.4):
    """
    Compute a 0–100 drowsiness score from EAR, MAR, and recent EAR history.

    Parameters:
        ear        : current EAR value
        mar        : current MAR value
        ear_history: list of recent EAR values (last N frames)
        ear_thresh : threshold below which eyes are considered closed
        mar_thresh : threshold above which mouth is considered open (yawn)

    Returns:
        int: drowsiness score 0 (fully alert) to 100 (extremely drowsy)
    """
    score = 0

    # EAR contribution: how much below threshold?
    if len(ear_history) > 0:
        closed_ratio = sum(1 for e in ear_history if e < ear_thresh) / len(ear_history)
        score += int(closed_ratio * 70)   # up to 70 points from eye closure

    # MAR contribution: yawning?
    if mar > mar_thresh:
        yawn_intensity = min((mar - mar_thresh) / 0.3, 1.0)
        score += int(yawn_intensity * 30)  # up to 30 points from yawning

    return min(score, 100)
