from flask import Flask, Response, send_file, jsonify
from picamera2 import Picamera2
import cv2
import time
import io
from datetime import datetime
import threading

app = Flask(__name__)

# Initialize camera
picam2 = Picamera2()
video_config = picam2.create_video_configuration(main={"size": (1280, 720)})  # Streaming resolution
still_config = picam2.create_still_configuration(main={"size": (3280, 2464)})  # High-res for photos
picam2.configure(video_config)
picam2.start()

# Global variable to track current mode
current_mode = "video"  # "video" or "photo"
mode_lock = threading.Lock()

def generate_frames():
    while True:
        # Capture frame
        frame = picam2.capture_array()
        # Convert to JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        # Yield frame in MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/capture_photo')
def capture_photo():
    """Capture a high-resolution still photo while maintaining stream"""
    try:
        with mode_lock:
            # Briefly pause the stream
            picam2.stop()
            
            # Configure for high-res capture
            picam2.configure(still_config)
            picam2.start()
            
            # Small delay for camera to adjust
            time.sleep(0.2)
            
            # Capture the photo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"photo_{timestamp}.jpg"
            
            # Capture to memory
            stream = io.BytesIO()
            picam2.capture_file(stream, format='jpeg')
            stream.seek(0)
            
            # Quickly switch back to video mode for streaming
            picam2.stop()
            picam2.configure(video_config)
            picam2.start()
            
            return send_file(stream, mimetype='image/jpeg', as_attachment=True, download_name=filename)
    
    except Exception as e:
        # Ensure camera is back in video mode if something goes wrong
        try:
            picam2.stop()
            picam2.configure(video_config)
            picam2.start()
        except:
            pass
        return jsonify({"error": f"Photo capture failed: {str(e)}"}), 500

@app.route('/capture_photo_stationary')
def capture_photo_stationary():
    """Capture high-res photo during stationary periods - optimized for movement operations"""
    try:
        with mode_lock:
            # Get current timestamp for filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"stationary_{timestamp}.jpg"
            
            # Temporarily stop streaming
            picam2.stop()
            
            # Switch to high-resolution still configuration
            picam2.configure(still_config)
            picam2.start()
            
            # Allow camera to stabilize (important after movement)
            time.sleep(0.5)
            
            # Capture high-resolution image
            stream = io.BytesIO()
            picam2.capture_file(stream, format='jpeg')
            stream.seek(0)
            
            # Resume video streaming
            picam2.stop()
            picam2.configure(video_config)
            picam2.start()
            
            return send_file(stream, mimetype='image/jpeg', as_attachment=True, download_name=filename)
            
    except Exception as e:
        # Ensure video mode is restored
        try:
            picam2.stop()
            picam2.configure(video_config)
            picam2.start()
        except:
            pass
        return jsonify({"error": f"Stationary photo capture failed: {str(e)}"}), 500

@app.route('/switch_mode/<mode>')
def switch_mode(mode):
    """Switch between video and photo modes"""
    global current_mode
    
    if mode not in ['video', 'photo']:
        return jsonify({"error": "Invalid mode. Use 'video' or 'photo'"}), 400
    
    with mode_lock:
        if mode != current_mode:
            picam2.stop()
            if mode == 'video':
                picam2.configure(video_config)
            else:
                picam2.configure(still_config)
            picam2.start()
            current_mode = mode
    
    return jsonify({"mode": current_mode, "message": f"Switched to {mode} mode"})

@app.route('/status')
def status():
    """Get current camera status"""
    return jsonify({
        "current_mode": current_mode,
        "streaming": True,
        "ready_for_capture": True
    })

@app.route('/health')
def health():
    """Simple health check endpoint"""
    try:
        # Check if camera is responsive
        return jsonify({
            "status": "healthy",
            "current_mode": current_mode,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

if __name__ == '__main__':
    # Run on port 5000, accessible from any IP on the network
    app.run(host='0.0.0.0', port=5000, threaded=True)
