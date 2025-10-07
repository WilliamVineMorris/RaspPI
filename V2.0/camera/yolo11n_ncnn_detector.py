"""
YOLO11n NCNN Object Detection for Autofocus Window Positioning

Uses YOLO11n in NCNN format for optimal Raspberry Pi performance.
NCNN provides hardware acceleration and efficient inference on ARM platforms.

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


class YOLO11nNCNNDetector:
    """YOLO11n NCNN-based object detector for focus window positioning"""
    
    def __init__(self, config: dict):
        """
        Initialize YOLO11n NCNN detector
        
        Args:
            config: YOLO detection configuration dict
        """
        self.config = config
        self.net = None
        self.model_loaded = False
        
        # Detection parameters
        self.confidence_threshold = config.get('confidence_threshold', 0.25)
        self.target_class = config.get('target_class', None)
        self.padding = config.get('padding', 0.1)
        self.min_area = config.get('min_area', 0.05)
        self.iou_threshold = config.get('iou_threshold', 0.45)
        
        # Model paths
        self.model_param = config.get('model_param', 'models/yolo11n_ncnn_model/model.ncnn.param')
        self.model_bin = config.get('model_bin', 'models/yolo11n_ncnn_model/model.ncnn.bin')
        
        # Output directory for detection visualizations
        self.output_dir = Path(config.get('detection_output_dir', 'calibration/focus_detection'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # YOLO11 class names (COCO dataset)
        self.class_names = [
            'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
            'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat',
            'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
            'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
            'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
            'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
            'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair',
            'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
            'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator',
            'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
        ]
        
        logger.info(f"🎯 YOLO11n NCNN Detector initialized: confidence={self.confidence_threshold}, padding={self.padding}")
    
    def load_model(self) -> bool:
        """
        Load YOLO11n NCNN model (lazy loading - only when needed)
        
        Returns:
            True if model loaded successfully
        """
        if self.model_loaded:
            return True
        
        try:
            import ncnn
            
            # Check if model files exist
            param_path = Path(self.model_param)
            bin_path = Path(self.model_bin)
            
            if not param_path.exists():
                logger.error(f"❌ NCNN param file not found: {param_path}")
                logger.info("📥 Please convert YOLO11n to NCNN format:")
                logger.info("   1. Ensure yolo11n.pt exists in models/ directory")
                logger.info("   2. Run: python3 convert_yolo_to_ncnn.py")
                logger.info("   Or manually: python3 -c \"from ultralytics import YOLO; YOLO('models/yolo11n.pt').export(format='ncnn')\"")
                return False
            
            if not bin_path.exists():
                logger.error(f"❌ NCNN bin file not found: {bin_path}")
                return False
            
            logger.info(f"📂 Loading YOLO11n NCNN model from {param_path.parent}")
            
            # Initialize NCNN network
            self.net = ncnn.Net()
            
            # Enable optimization for ARM
            self.net.opt.use_vulkan_compute = False  # Disable Vulkan for better Pi compatibility
            self.net.opt.use_fp16_packed = True      # Use FP16 for faster inference
            self.net.opt.use_fp16_storage = True
            self.net.opt.use_fp16_arithmetic = True
            self.net.opt.use_packing_layout = True
            
            # Set thread count (adjust based on Pi cores)
            self.net.opt.num_threads = 4  # Pi 5 has 4 cores
            
            # Load model
            self.net.load_param(str(param_path))
            self.net.load_model(str(bin_path))
            
            self.model_loaded = True
            logger.info("✅ YOLO11n NCNN model loaded successfully")
            return True
            
        except ImportError:
            logger.error("❌ ncnn-python not installed. Install with: pip install ncnn")
            logger.info("   Or build from source: https://github.com/Tencent/ncnn/tree/master/python")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to load YOLO11n NCNN model: {e}")
            return False
    
    def _preprocess_image(self, image: np.ndarray, target_size: int = 640) -> Tuple[ncnn.Mat, float]:
        """
        Preprocess image for YOLO11n inference
        
        Args:
            image: Input image (H, W, C) BGR format
            target_size: Target size for YOLO input (default 640)
        
        Returns:
            Tuple of (ncnn.Mat, scale_factor)
        """
        import ncnn
        
        h, w = image.shape[:2]
        
        # Calculate scale to fit target size while maintaining aspect ratio
        scale = min(target_size / w, target_size / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # Resize image
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Create padded image (letterbox)
        padded = np.zeros((target_size, target_size, 3), dtype=np.uint8)
        pad_w = (target_size - new_w) // 2
        pad_h = (target_size - new_h) // 2
        padded[pad_h:pad_h+new_h, pad_w:pad_w+new_w] = resized
        
        # Convert to NCNN Mat (RGB, normalized to 0-1)
        mat_in = ncnn.Mat.from_pixels(padded, ncnn.Mat.PixelType.PIXEL_BGR2RGB, target_size, target_size)
        
        # Normalize (YOLO expects values in 0-1 range)
        mean_vals = [0.0, 0.0, 0.0]
        norm_vals = [1/255.0, 1/255.0, 1/255.0]
        mat_in.substract_mean_normalize(mean_vals, norm_vals)
        
        return mat_in, scale
    
    def _postprocess_detections(self, outputs: List, scale: float, original_size: Tuple[int, int], 
                                target_size: int = 640) -> List[Tuple[int, int, int, int, float, int]]:
        """
        Post-process YOLO11n NCNN outputs to get bounding boxes
        
        Args:
            outputs: NCNN network outputs
            scale: Scale factor used in preprocessing
            original_size: Original image size (width, height)
            target_size: Target size used in preprocessing
        
        Returns:
            List of detections: [(x1, y1, x2, y2, confidence, class_id), ...]
        """
        detections = []
        
        # YOLO11n output format: [batch, 84, 8400]
        # First 4 values: [x_center, y_center, width, height]
        # Remaining 80 values: class confidences
        
        output = np.array(outputs[0])  # Get first output
        
        # Transpose to [8400, 84]
        if len(output.shape) == 3:
            output = output[0]  # Remove batch dimension
        output = output.T
        
        # Extract boxes and scores
        boxes = output[:, :4]
        scores = output[:, 4:]
        
        # Get class with max confidence for each detection
        class_ids = np.argmax(scores, axis=1)
        confidences = np.max(scores, axis=1)
        
        # Filter by confidence threshold
        mask = confidences > self.confidence_threshold
        boxes = boxes[mask]
        confidences = confidences[mask]
        class_ids = class_ids[mask]
        
        # Convert from center format to corner format
        pad_w = (target_size - int(original_size[0] * scale)) // 2
        pad_h = (target_size - int(original_size[1] * scale)) // 2
        
        for box, conf, cls_id in zip(boxes, confidences, class_ids):
            x_center, y_center, width, height = box
            
            # Convert to corner coordinates and remove padding
            x1 = int((x_center - width / 2 - pad_w) / scale)
            y1 = int((y_center - height / 2 - pad_h) / scale)
            x2 = int((x_center + width / 2 - pad_w) / scale)
            y2 = int((y_center + height / 2 - pad_h) / scale)
            
            # Clamp to image bounds
            x1 = max(0, min(x1, original_size[0]))
            y1 = max(0, min(y1, original_size[1]))
            x2 = max(0, min(x2, original_size[0]))
            y2 = max(0, min(y2, original_size[1]))
            
            detections.append((x1, y1, x2, y2, float(conf), int(cls_id)))
        
        # Apply NMS (Non-Maximum Suppression)
        if len(detections) > 0:
            detections = self._apply_nms(detections)
        
        return detections
    
    def _apply_nms(self, detections: List[Tuple[int, int, int, int, float, int]]) -> List[Tuple[int, int, int, int, float, int]]:
        """Apply Non-Maximum Suppression to remove overlapping boxes"""
        if len(detections) == 0:
            return []
        
        boxes = np.array([[d[0], d[1], d[2], d[3]] for d in detections])
        scores = np.array([d[4] for d in detections])
        
        # OpenCV NMS
        indices = cv2.dnn.NMSBoxes(
            boxes.tolist(), 
            scores.tolist(), 
            self.confidence_threshold, 
            self.iou_threshold
        )
        
        if len(indices) > 0:
            return [detections[i] for i in indices.flatten()]
        return []
    
    def detect_object(self, image_array: np.ndarray, camera_id: str = "camera0") -> Optional[Tuple[float, float, float, float]]:
        """
        Detect primary object in image and return bounding box
        
        Args:
            image_array: Image as numpy array (H, W, C) in RGB or BGR format
            camera_id: Camera identifier for saving visualization
        
        Returns:
            Tuple of (x_start, y_start, width, height) as fractions (0.0-1.0), or None if no detection
        """
        if not self.model_loaded:
            if not self.load_model():
                logger.warning("⚠️ YOLO11n NCNN model not available, cannot detect object")
                return None
        
        try:
            import ncnn
            
            # Convert RGB to BGR if needed (NCNN expects BGR)
            if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                # Check if image is RGB (typical for Pi camera)
                # Simple heuristic: if red channel has higher values, assume RGB
                if np.mean(image_array[:, :, 0]) > np.mean(image_array[:, :, 2]):
                    image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
                else:
                    image_bgr = image_array
            else:
                logger.error("❌ Invalid image format (expected H×W×3)")
                return None
            
            img_height, img_width = image_bgr.shape[:2]
            logger.debug(f"📷 Processing image: {img_width}×{img_height}")
            
            # Preprocess image
            mat_in, scale = self._preprocess_image(image_bgr)
            
            # Run inference
            extractor = self.net.create_extractor()
            extractor.input("in0", mat_in)  # YOLO11n input name
            
            ret, mat_out = extractor.extract("out0")  # YOLO11n output name
            
            if ret != 0:
                logger.error(f"❌ NCNN extraction failed with code: {ret}")
                return None
            
            # Convert NCNN Mat to numpy
            output_data = np.array(mat_out)
            
            # Post-process detections
            detections = self._postprocess_detections([output_data], scale, (img_width, img_height))
            
            if len(detections) == 0:
                logger.warning("⚠️ No objects detected in image")
                return None
            
            # Filter by target class if specified
            if self.target_class:
                target_class_id = self.class_names.index(self.target_class) if self.target_class in self.class_names else -1
                detections = [d for d in detections if d[5] == target_class_id]
                
                if len(detections) == 0:
                    logger.warning(f"⚠️ No '{self.target_class}' objects detected")
                    return None
            
            # Get highest confidence detection
            best_detection = max(detections, key=lambda d: d[4])
            x1, y1, x2, y2, confidence, class_id = best_detection
            
            # Calculate bounding box dimensions
            bbox_width = x2 - x1
            bbox_height = y2 - y1
            bbox_area = (bbox_width * bbox_height) / (img_width * img_height)
            
            # Validate minimum area
            if bbox_area < self.min_area:
                logger.warning(f"⚠️ Detected object too small: {bbox_area:.1%} < {self.min_area:.1%}")
                return None
            
            # Get class name
            class_name = self.class_names[class_id] if class_id < len(self.class_names) else f"class_{class_id}"
            
            # Convert to fractional coordinates (0.0-1.0)
            x_start_frac = x1 / img_width
            y_start_frac = y1 / img_height
            width_frac = bbox_width / img_width
            height_frac = bbox_height / img_height
            
            # Add padding
            x_start_frac = max(0.0, x_start_frac - self.padding * width_frac)
            y_start_frac = max(0.0, y_start_frac - self.padding * height_frac)
            width_frac = min(1.0 - x_start_frac, width_frac * (1 + 2 * self.padding))
            height_frac = min(1.0 - y_start_frac, height_frac * (1 + 2 * self.padding))
            
            logger.info(f"✅ Object detected: {class_name} (confidence={confidence:.2f}, area={bbox_area:.1%})")
            logger.info(f"   Focus window: [{x_start_frac:.3f}, {y_start_frac:.3f}, {width_frac:.3f}, {height_frac:.3f}]")
            
            # Save visualization
            self._save_detection_visualization(
                image_bgr, detections, best_detection, camera_id,
                (x_start_frac, y_start_frac, width_frac, height_frac)
            )
            
            return (x_start_frac, y_start_frac, width_frac, height_frac)
            
        except Exception as e:
            logger.error(f"❌ YOLO11n detection failed: {e}", exc_info=True)
            return None
    
    def _save_detection_visualization(self, image: np.ndarray, detections: List, 
                                     best_detection: Tuple, camera_id: str,
                                     focus_window: Tuple[float, float, float, float]):
        """
        Save visualization image with bounding boxes and focus window
        
        Args:
            image: Original image (BGR)
            detections: All detections
            best_detection: Selected best detection
            camera_id: Camera identifier
            focus_window: Focus window as fractions (x, y, w, h)
        """
        try:
            # Create visualization image
            vis_image = image.copy()
            h, w = vis_image.shape[:2]
            
            # Draw all detections in light blue
            for det in detections:
                x1, y1, x2, y2, conf, cls_id = det
                color = (255, 200, 100)  # Light blue
                thickness = 1
                
                # Draw box
                cv2.rectangle(vis_image, (x1, y1), (x2, y2), color, thickness)
                
                # Draw label
                class_name = self.class_names[cls_id] if cls_id < len(self.class_names) else f"class_{cls_id}"
                label = f"{class_name}: {conf:.2f}"
                label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(vis_image, (x1, y1 - label_size[1] - 4), 
                            (x1 + label_size[0], y1), color, -1)
                cv2.putText(vis_image, label, (x1, y1 - 2), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            
            # Draw best detection in bright green (thicker)
            x1, y1, x2, y2, conf, cls_id = best_detection
            color = (0, 255, 0)  # Bright green
            thickness = 3
            
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), color, thickness)
            
            # Draw "SELECTED" label
            class_name = self.class_names[cls_id] if cls_id < len(self.class_names) else f"class_{cls_id}"
            label = f"SELECTED: {class_name} ({conf:.2f})"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(vis_image, (x1, y1 - label_size[1] - 8), 
                        (x1 + label_size[0] + 4, y1), color, -1)
            cv2.putText(vis_image, label, (x1 + 2, y1 - 4), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            
            # Draw focus window in yellow (dashed)
            fx_start = int(focus_window[0] * w)
            fy_start = int(focus_window[1] * h)
            fw = int(focus_window[2] * w)
            fh = int(focus_window[3] * h)
            
            focus_color = (0, 255, 255)  # Yellow
            self._draw_dashed_rectangle(vis_image, (fx_start, fy_start), 
                                        (fx_start + fw, fy_start + fh), focus_color, 2)
            
            # Add focus window label
            focus_label = "FOCUS WINDOW"
            cv2.putText(vis_image, focus_label, (fx_start, fy_start - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, focus_color, 2)
            
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
            self.net = None
            self.model_loaded = False
            logger.info("🗑️ YOLO11n NCNN model unloaded")
