"""
YOLO11n Object Detection for Autofocus Window Positioning

Uses YOLO11n PyTorch model via Ultralytics for object detection.
Simpler than NCNN and avoids binary dependency conflicts.

Detects objects in camera frame to dynamically position AfWindows during calibration.
Saves bounding box visualization images to calibration directory.
"""

import logging
import cv2
import numpy as np
from typing import Optional, Tuple, List
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class YOLO11nDetector:
    """YOLO11n PyTorch-based object detector for focus window positioning"""
    
    def __init__(self, config: dict):
        """
        Initialize YOLO11n detector
        
        Args:
            config: YOLO detection configuration dict
        """
        self.config = config
        self.model = None
        self.model_loaded = False
        
        # Detection parameters
        self.confidence_threshold = config.get('confidence_threshold', 0.25)
        self.target_class = config.get('target_class', None)
        self.padding = config.get('padding', 0.1)
        self.min_area = config.get('min_area', 0.05)
        self.iou_threshold = config.get('iou_threshold', 0.45)
        
        # Model path
        self.model_path = config.get('model_path', 'models/yolo11n.pt')
        
        # Output directory for detection visualizations
        self.output_dir = Path(config.get('detection_output_dir', 'calibration/focus_detection'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🎯 YOLO11n Detector initialized: confidence={self.confidence_threshold}, padding={self.padding}")
    
    def load_model(self) -> bool:
        """
        Load YOLO11n model (lazy loading - only when needed)
        
        Returns:
            True if model loaded successfully
        """
        if self.model_loaded:
            return True
        
        try:
            from ultralytics import YOLO
            
            # Check if model file exists
            model_path = Path(self.model_path)
            
            if not model_path.exists():
                logger.error(f"❌ YOLO model file not found: {model_path}")
                logger.info("📥 Please ensure yolo11n.pt exists in models/ directory")
                logger.info("   Download from: https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt")
                return False
            
            logger.info(f"📂 Loading YOLO11n model from {model_path}")
            
            # Load model
            self.model = YOLO(str(model_path))
            
            # Configure model for inference
            self.model.conf = self.confidence_threshold
            self.model.iou = self.iou_threshold
            
            self.model_loaded = True
            logger.info("✅ YOLO11n model loaded successfully")
            return True
            
        except ImportError:
            logger.error("❌ ultralytics package not installed. Install with: pip install ultralytics")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to load YOLO11n model: {e}")
            return False
    
    def detect_object(self, image: np.ndarray, camera_id: str) -> Optional[Tuple[float, float, float, float]]:
        """
        Detect object in image and return focus window coordinates
        
        Args:
            image: Input image (RGB format from Picamera2)
            camera_id: Camera identifier for logging/visualization
            
        Returns:
            Focus window as (x_start, y_start, width, height) in fractions (0.0-1.0)
            or None if no suitable object detected
        """
        # Load model if needed
        if not self.model_loaded:
            if not self.load_model():
                logger.error("❌ Cannot detect objects - model not loaded")
                return None
        
        try:
            # Run inference
            logger.debug(f"🔍 Running YOLO detection on {image.shape} image...")
            results = self.model(image, verbose=False)
            
            # Get detections
            detections = results[0].boxes
            
            if len(detections) == 0:
                logger.warning(f"⚠️ No objects detected in image")
                return None
            
            # Filter and select best detection
            best_detection = self._select_best_detection(detections, image.shape)
            
            if best_detection is None:
                logger.warning(f"⚠️ No suitable object found after filtering")
                return None
            
            # Convert detection to focus window
            focus_window = self._detection_to_focus_window(best_detection, image.shape)
            
            # Save visualization
            self._save_visualization(image, results[0], best_detection, focus_window, camera_id)
            
            logger.info(f"✅ YOLO detection successful: focus window {focus_window}")
            return focus_window
            
        except Exception as e:
            logger.error(f"❌ YOLO detection failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _select_best_detection(self, detections, image_shape: Tuple[int, int, int]) -> Optional[dict]:
        """
        Select the best detection from all detected objects
        
        Args:
            detections: YOLOv11 detection results
            image_shape: Image shape (H, W, C)
            
        Returns:
            Best detection dict with bbox, confidence, class_id, class_name
        """
        h, w = image_shape[:2]
        image_area = h * w
        
        candidates = []
        
        for i, det in enumerate(detections):
            # Extract detection info
            bbox = det.xyxy[0].cpu().numpy()  # [x1, y1, x2, y2]
            conf = float(det.conf[0])
            class_id = int(det.cls[0])
            class_name = self.model.names[class_id]
            
            # Calculate area
            box_w = bbox[2] - bbox[0]
            box_h = bbox[3] - bbox[1]
            area = box_w * box_h
            area_fraction = area / image_area
            
            # Filter by minimum area
            if area_fraction < self.min_area:
                logger.debug(f"   Skipping {class_name} (area={area_fraction:.3f} < min={self.min_area})")
                continue
            
            # Filter by target class if specified
            if self.target_class is not None and class_name != self.target_class:
                logger.debug(f"   Skipping {class_name} (not target class '{self.target_class}')")
                continue
            
            # Filter by confidence
            if conf < self.confidence_threshold:
                continue
            
            candidates.append({
                'index': i,  # Add index for comparison
                'bbox': bbox,
                'confidence': conf,
                'class_id': class_id,
                'class_name': class_name,
                'area': area,
                'area_fraction': area_fraction
            })
        
        if not candidates:
            return None
        
        # Select best: highest confidence * area
        best = max(candidates, key=lambda x: x['confidence'] * x['area_fraction'])
        
        logger.info(f"🎯 YOLO detection found {len(candidates)} suitable object(s)")
        for i, cand in enumerate(candidates, 1):
            marker = "→" if cand['index'] == best['index'] else " "
            logger.info(f"   {marker} {i}. {cand['class_name']} (conf={cand['confidence']:.2f}, area={cand['area_fraction']*100:.1f}%)")
        
        return best
    
    def _detection_to_focus_window(self, detection: dict, image_shape: Tuple[int, int, int]) -> Tuple[float, float, float, float]:
        """
        Convert detection bounding box to focus window with padding
        
        Args:
            detection: Detection dict with bbox
            image_shape: Image shape (H, W, C)
            
        Returns:
            Focus window (x_start, y_start, width, height) as fractions
        """
        h, w = image_shape[:2]
        bbox = detection['bbox']
        
        # Get bounding box in pixels
        x1, y1, x2, y2 = bbox
        box_w = x2 - x1
        box_h = y2 - y1
        
        # Add padding
        pad_w = box_w * self.padding
        pad_h = box_h * self.padding
        
        # Calculate padded box
        padded_x1 = max(0, x1 - pad_w)
        padded_y1 = max(0, y1 - pad_h)
        padded_x2 = min(w, x2 + pad_w)
        padded_y2 = min(h, y2 + pad_h)
        
        # Convert to fractions
        focus_x = padded_x1 / w
        focus_y = padded_y1 / h
        focus_w = (padded_x2 - padded_x1) / w
        focus_h = (padded_y2 - padded_y1) / h
        
        return (focus_x, focus_y, focus_w, focus_h)
    
    def _save_visualization(self, image: np.ndarray, results, best_detection: dict, 
                          focus_window: Tuple[float, float, float, float], camera_id: str):
        """
        Save detection visualization with bounding boxes
        
        Args:
            image: Original image
            results: YOLO results object
            best_detection: Selected detection
            focus_window: Calculated focus window
            camera_id: Camera identifier
        """
        try:
            # Create annotated image
            vis_image = results.plot()
            
            # Draw focus window on top
            h, w = image.shape[:2]
            fx, fy, fw, fh = focus_window
            
            # Convert focus window to pixels
            fx_px = int(fx * w)
            fy_px = int(fy * h)
            fw_px = int(fw * w)
            fh_px = int(fh * h)
            
            # Draw dashed yellow rectangle for focus window
            color = (0, 255, 255)  # Yellow in BGR
            self._draw_dashed_rectangle(
                vis_image,
                (fx_px, fy_px),
                (fx_px + fw_px, fy_px + fh_px),
                color,
                3
            )
            
            # Add text label
            cv2.putText(vis_image, "Focus Window", 
                       (fx_px + 5, fy_px + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            # Save image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{camera_id}_detection_{timestamp}.jpg"
            filepath = self.output_dir / filename
            
            cv2.imwrite(str(filepath), vis_image)
            logger.info(f"💾 Saved detection visualization: {filepath}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save detection visualization: {e}")
    
    def _draw_dashed_rectangle(self, img: np.ndarray, pt1: Tuple[int, int], 
                              pt2: Tuple[int, int], color: Tuple[int, int, int], 
                              thickness: int, dash_length: int = 10):
        """Draw dashed rectangle"""
        x1, y1 = pt1
        x2, y2 = pt2
        
        # Top line
        for i in range(x1, x2, dash_length * 2):
            cv2.line(img, (i, y1), (min(i + dash_length, x2), y1), color, thickness)
        
        # Bottom line
        for i in range(x1, x2, dash_length * 2):
            cv2.line(img, (i, y2), (min(i + dash_length, x2), y2), color, thickness)
        
        # Left line
        for i in range(y1, y2, dash_length * 2):
            cv2.line(img, (x1, i), (x1, min(i + dash_length, y2)), color, thickness)
        
        # Right line
        for i in range(y1, y2, dash_length * 2):
            cv2.line(img, (x2, i), (x2, min(i + dash_length, y2)), color, thickness)
    
    def unload_model(self):
        """Unload model to free memory"""
        if self.model_loaded:
            self.model = None
            self.model_loaded = False
            logger.info("🗑️ YOLO11n model unloaded")
