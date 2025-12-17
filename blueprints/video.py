import io
import os
import cv2
import numpy as np
import threading
import time
from datetime import datetime
from flask import Blueprint, jsonify, request, send_file, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
import json

video_bp = Blueprint('video', __name__)

# Store frames per device
device_frames = {}
device_frames_lock = threading.Lock()
device_last_update = {}

# Store face detection/recognition results
device_detections = {}
device_detections_lock = threading.Lock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Move up one level to the project root (web_backend/) and into models/
MODEL_DIR = os.path.join(BASE_DIR, "..", "models")

PROTOTXT_PATH = os.path.join(MODEL_DIR, "deploy.prototxt")
MODEL_PATH = os.path.join(MODEL_DIR, "res10_300x300_ssd_iter_140000.caffemodel")

# Load face detection model
face_net = cv2.dnn.readNetFromCaffe(PROTOTXT_PATH, MODEL_PATH)

def detect_faces(frame_bytes):
    """Detect faces in frame using DNN"""
    try:
        # Convert bytes to numpy array
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return []
        
        (h, w) = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0,
                                     (300, 300), (104.0, 177.0, 123.0))
        
        face_net.setInput(blob)
        detections = face_net.forward()
        
        faces = []
        for i in range(0, detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            
            if confidence > 0.5:  # Confidence threshold
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (startX, startY, endX, endY) = box.astype("int")
                
                # Ensure bounding boxes fall within the dimensions of the frame
                startX = max(0, startX)
                startY = max(0, startY)
                endX = min(w, endX)
                endY = min(h, endY)
                
                faces.append({
                    'box': [int(startX), int(startY), int(endX), int(endY)],
                    'confidence': float(confidence)
                })
        
        return faces
    except Exception as e:
        print(f"[ERROR] Face detection failed: {e}")
        return []

@video_bp.route('/stream/start', methods=['POST'])
@jwt_required()
def start_stream():
    """Initialize stream for a device"""
    user_id = get_jwt_identity()
    data = request.get_json()
    device_id = data.get('deviceId')
    
    if not device_id:
        return jsonify({'error': 'deviceId required'}), 400
    
    with device_frames_lock:
        device_frames[device_id] = {
            'frame': None,
            'timestamp': None,
            'user_id': user_id
        }
        device_last_update[device_id] = datetime.utcnow()
    
    return jsonify({
        'message': 'Stream initialized',
        'deviceId': device_id,
        'stream_url': f'/api/video/stream/{device_id}'
    }), 200

@video_bp.route('/stream/<device_id>/frame', methods=['POST'])
def post_device_frame(device_id):
    """Receive frame from Raspberry Pi device"""
    if 'frame' not in request.files:
        return jsonify({'error': 'no frame provided'}), 400
    
    file = request.files['frame']
    img_bytes = file.read()
    
    # Detect faces
    faces = detect_faces(img_bytes)
    
    with device_frames_lock:
        if device_id not in device_frames:
            device_frames[device_id] = {
                'frame': None,
                'timestamp': None,
                'user_id': None
            }
        
        device_frames[device_id]['frame'] = img_bytes
        device_frames[device_id]['timestamp'] = datetime.utcnow()
        device_last_update[device_id] = datetime.utcnow()
    
    with device_detections_lock:
        device_detections[device_id] = {
            'faces': faces,
            'timestamp': datetime.utcnow()
        }
    
    return jsonify({
        'status': 'ok',
        'deviceId': device_id,
        'faces_detected': len(faces),
        'timestamp': datetime.utcnow().isoformat()
    }), 200

@video_bp.route('/stream/<device_id>/frame', methods=['GET'])
@jwt_required()
def get_device_frame(device_id):
    """Get latest frame for a specific device"""
    user_id = get_jwt_identity()
    
    with device_frames_lock:
        if device_id not in device_frames:
            return jsonify({'error': 'Device stream not found'}), 404
        
        # Check authorization
        device_info = device_frames[device_id]
        if device_info['user_id'] and device_info['user_id'] != user_id:
            return jsonify({'error': 'Unauthorized to access this stream'}), 403
        
        frame_bytes = device_info['frame']
        timestamp = device_info['timestamp']
        
        if not frame_bytes:
            return jsonify({'available': False}), 404
    
    # Return as JPEG
    buf = io.BytesIO(frame_bytes)
    return send_file(
        buf,
        mimetype='image/jpeg',
        as_attachment=False,
        download_name=f'frame_{device_id}_{timestamp}.jpg' if timestamp else 'frame.jpg'
    )

@video_bp.route('/stream/<device_id>/detections', methods=['GET'])
@jwt_required()
def get_device_detections(device_id):
    """Get face detection results for a device"""
    user_id = get_jwt_identity()
    
    with device_frames_lock:
        if device_id not in device_frames:
            return jsonify({'error': 'Device stream not found'}), 404
        
        device_info = device_frames[device_id]
        if device_info['user_id'] and device_info['user_id'] != user_id:
            return jsonify({'error': 'Unauthorized'}), 403
    
    with device_detections_lock:
        detections = device_detections.get(device_id, {'faces': [], 'timestamp': None})
    
    return jsonify(detections), 200

@video_bp.route('/stream/<device_id>/live', methods=['GET'])
def stream_device_live(device_id):
    """Live video stream (MJPEG) for a specific device"""
    def generate():
        while True:
            with device_frames_lock:
                if device_id in device_frames and device_frames[device_id]['frame']:
                    frame_bytes = device_frames[device_id]['frame']
                else:
                    time.sleep(0.1)
                    continue
            
            # Send MJPEG frame
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.033)  # ~30 FPS
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@video_bp.route('/stream/<device_id>/info', methods=['GET'])
@jwt_required()
def get_stream_info(device_id):
    """Get stream information and status"""
    with device_frames_lock:
        if device_id not in device_frames:
            return jsonify({'error': 'Stream not found'}), 404
        
        last_update = device_last_update.get(device_id)
        is_active = False
        if last_update:
            time_diff = (datetime.utcnow() - last_update).total_seconds()
            is_active = time_diff < 5  # Consider active if updated in last 5 seconds
        
        return jsonify({
            'deviceId': device_id,
            'active': is_active,
            'last_update': last_update.isoformat() if last_update else None,
            'has_frame': device_frames[device_id]['frame'] is not None
        }), 200

@video_bp.route('/stream/<device_id>/stop', methods=['POST'])
@jwt_required()
def stop_stream(device_id):
    """Stop streaming for a device"""
    user_id = get_jwt_identity()
    
    with device_frames_lock:
        if device_id in device_frames:
            # Check authorization
            if device_frames[device_id]['user_id'] and device_frames[device_id]['user_id'] != user_id:
                return jsonify({'error': 'Unauthorized'}), 403
            
            del device_frames[device_id]
    
    if device_id in device_last_update:
        del device_last_update[device_id]
    
    if device_id in device_detections:
        del device_detections[device_id]
    
    return jsonify({'message': 'Stream stopped', 'deviceId': device_id}), 200