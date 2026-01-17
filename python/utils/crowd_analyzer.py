import cv2
import numpy as np

class CrowdAnalyzer:
    @staticmethod
    def analyze(frame):
        """Advanced crowd density analysis"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (21, 21), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter valid people contours
        valid_contours = [c for c in contours if 800 < cv2.contourArea(c) < 50000]
        count = len(valid_contours)
        
        total_area = frame.shape[0] * frame.shape[1]
        crowd_area = sum(cv2.contourArea(c) for c in valid_contours)
        density = min((crowd_area / total_area) * 100, 100)
        
        return {
            'count': count,
            'density': round(density, 1),
            'free_space': round(100 - density, 1),
            'status': 'HIGH CROWD' if density > 40 else 'NORMAL'
        }