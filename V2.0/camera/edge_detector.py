"""
Edge-based object detection for focus window positioning

This module uses computer vision edge detection (Canny) to find objects on the turntable
without requiring trained AI models. More reliable than YOLO for generic object detection.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)


class EdgeDetector:
    """Edge-based object detector for focus window positioning"""
    
    def __init__(self, config: dict):
        """
        Initialize edge detector
        
        Args:
            config: Edge detection configuration dict
        """
        self.config = config
        
        # Search parameters
        self.search_region = config.get('search_region', 0.7)  # Center 70%
        
        # Edge detection parameters
        self.gaussian_blur = config.get('gaussian_blur', 5)
        self.canny_threshold1 = config.get('canny_threshold1', 50)
        self.canny_threshold2 = config.get('canny_threshold2', 150)
        
        # Object selection
        self.min_contour_area = config.get('min_contour_area', 0.01)  # 1% of image
        self.max_contour_area = config.get('max_contour_area', 0.5)   # 50% of image
        self.padding = config.get('padding', 0.2)
        
        # Output directory for visualizations
        self.output_dir = Path(config.get('detection_output_dir', 'calibration/edge_detection'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🔍 Edge Detector initialized: search_region={self.search_region}, "
                   f"canny=({self.canny_threshold1}, {self.canny_threshold2})")
    
    def detect_object(self, image: np.ndarray, camera_name: str = "camera") -> Optional[Tuple[int, int, int, int]]:
        """
        Detect object using edge detection in center region
        
        Args:
            image: RGB image array (H, W, C)
            camera_name: Camera identifier for logging/saving
            
        Returns:
            Focus window as (x, y, width, height) in pixels, or None if detection fails
        """
        try:
            h, w = image.shape[:2]
            
            # Define search region (center area)
            region_size = int(min(h, w) * self.search_region)
            x_start = (w - region_size) // 2
            y_start = (h - region_size) // 2
            
            # Extract center region
            roi = image[y_start:y_start+region_size, x_start:x_start+region_size]
            
            # Convert to grayscale
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
            
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (self.gaussian_blur, self.gaussian_blur), 0)
            
            # Detect edges using Canny
            edges = cv2.Canny(blurred, self.canny_threshold1, self.canny_threshold2)
            
            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                logger.warning(f"⚠️ No edges detected in {camera_name} image")
                return None
            
            # Filter contours by area
            image_area = region_size * region_size
            min_area = image_area * self.min_contour_area
            max_area = image_area * self.max_contour_area
            
            valid_contours = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if min_area <= area <= max_area:
                    valid_contours.append({
                        'contour': contour,
                        'area': area,
                        'bbox': cv2.boundingRect(contour)
                    })
            
            if not valid_contours:
                logger.warning(f"⚠️ No valid contours found (area between {self.min_contour_area*100:.1f}% and {self.max_contour_area*100:.1f}%)")
                return None
            
            # Select largest valid contour
            best = max(valid_contours, key=lambda x: x['area'])
            bbox = best['bbox']  # (x, y, w, h) in ROI coordinates
            
            logger.info(f"🎯 Edge detection found {len(valid_contours)} object(s)")
            logger.info(f"   → Selected: area={best['area']/image_area*100:.1f}% at ({bbox[0]}, {bbox[1]})")
            
            # Convert ROI coordinates to full image coordinates
            x_roi, y_roi, w_bbox, h_bbox = bbox
            x_full = x_start + x_roi
            y_full = y_start + y_roi
            
            # Add padding
            pad_w = int(w_bbox * self.padding)
            pad_h = int(h_bbox * self.padding)
            
            x_padded = max(0, x_full - pad_w)
            y_padded = max(0, y_full - pad_h)
            w_padded = min(w - x_padded, w_bbox + 2 * pad_w)
            h_padded = min(h - y_padded, h_bbox + 2 * pad_h)
            
            focus_window = (x_padded, y_padded, w_padded, h_padded)
            
            # Save visualization
            self._save_visualization(image, roi, edges, valid_contours, best, focus_window, camera_name)
            
            return focus_window
            
        except Exception as e:
            logger.error(f"❌ Edge detection failed for {camera_name}: {e}", exc_info=True)
            return None
    
    def _save_visualization(self, image: np.ndarray, roi: np.ndarray, edges: np.ndarray,
                           valid_contours: list, best: dict, focus_window: Tuple[int, int, int, int],
                           camera_name: str):
        """
        Save visualization of edge detection results
        
        Args:
            image: Original full image
            roi: Region of interest used for detection
            edges: Canny edge detection result
            valid_contours: List of valid contour dicts
            best: Best selected contour dict
            focus_window: Final focus window in full image coordinates
            camera_name: Camera identifier
        """
        try:
            # Create visualization with 3 panels: Original, Edges, Result
            h, w = image.shape[:2]
            
            # Panel 1: Original image with search region outlined
            img_with_region = image.copy()
            region_size = roi.shape[0]
            x_start = (w - region_size) // 2
            y_start = (h - region_size) // 2
            cv2.rectangle(img_with_region, (x_start, y_start), 
                         (x_start + region_size, y_start + region_size), 
                         (255, 255, 0), 2)  # Yellow search region
            
            # Panel 2: Edge detection result
            edges_color = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
            
            # Panel 3: Final result with focus window
            img_result = image.copy()
            x, y, fw_w, fw_h = focus_window
            cv2.rectangle(img_result, (x, y), (x + fw_w, y + fw_h), (0, 255, 0), 3)  # Green focus window
            
            # Draw all valid contours in ROI
            roi_with_contours = cv2.cvtColor(roi.copy(), cv2.COLOR_GRAY2RGB) if len(roi.shape) == 2 else roi.copy()
            for contour_dict in valid_contours:
                color = (0, 255, 0) if contour_dict == best else (255, 255, 0)
                cv2.drawContours(roi_with_contours, [contour_dict['contour']], -1, color, 2)
            
            # Resize panels to same height for concatenation
            panel_h = 480
            panel_w = int(w * panel_h / h)
            
            panel1 = cv2.resize(img_with_region, (panel_w, panel_h))
            panel2 = cv2.resize(edges_color, (panel_w, panel_h))
            panel3 = cv2.resize(roi_with_contours, (panel_w, panel_h))
            panel4 = cv2.resize(img_result, (panel_w, panel_h))
            
            # Add labels
            cv2.putText(panel1, "1. Search Region", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.putText(panel2, "2. Edge Detection", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(panel3, "3. Contours Found", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(panel4, "4. Focus Window", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Concatenate panels horizontally (2x2 grid)
            row1 = np.hstack([panel1, panel2])
            row2 = np.hstack([panel3, panel4])
            visualization = np.vstack([row1, row2])
            
            # Save visualization
            output_path = self.output_dir / f"{camera_name}_edge_detection.jpg"
            cv2.imwrite(str(output_path), cv2.cvtColor(visualization, cv2.COLOR_RGB2BGR))
            logger.info(f"💾 Saved edge detection visualization: {output_path}")
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to save visualization: {e}")
    
    def get_focus_window_normalized(self, image: np.ndarray, camera_name: str = "camera") -> Optional[Tuple[float, float, float, float]]:
        """
        Detect object and return normalized focus window (0.0-1.0)
        
        Args:
            image: RGB image array
            camera_name: Camera identifier
            
        Returns:
            (x, y, width, height) as fractions of image size, or None
        """
        window = self.detect_object(image, camera_name)
        if window is None:
            return None
        
        h, w = image.shape[:2]
        x, y, fw_w, fw_h = window
        
        return (x / w, y / h, fw_w / w, fw_h / h)
