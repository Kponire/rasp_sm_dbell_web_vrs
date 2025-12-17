""" from flask import Blueprint, Response, jsonify, render_template_string, request, send_file
from flask_jwt_extended import jwt_required
from flask_jwt_extended import get_jwt_identity
from imutils.video import VideoStream
import numpy as np
import imutils
import time
import cv2
import os
from deepface import DeepFace
from pathlib import Path
from web_backend.models import db, Notification
from web_backend.config import Config
from datetime import datetime
from ..supabase_client import upload_image, list_user_images
from werkzeug.utils import secure_filename
from threading import Lock
import io

from web_backend.blueprints.notifications import initiate_call, send_email, send_push_notification

video_bp = Blueprint('video', __name__)

protoPath = os.path.sep.join(['face_detection_model', "deploy.prototxt"])
modelPath = os.path.sep.join(['face_detection_model', "res10_300x300_ssd_iter_140000.caffemodel"])
print("[INFO] loading face detection model...")
detector = None # cv2.dnn.readNetFromCaffe(protoPath, modelPath)

print("[INFO] loading face recognition model...")
KNOWN_FACES_DIR = "dataset"
UNKNOWN_LABEL = "Unknown"
CONFIDENCE_THRESHOLD = 0.6
RECOGNITION_THRESHOLD = 0.30 

MODEL_NAME = "Facenet512"  

Path(KNOWN_FACES_DIR).mkdir(exist_ok=True) 
# Global video stream state
vs = None
streaming = True
frame_counter = 0
recognized_faces = {}
last_action_time = {}
FRAME_SKIP = 3
known_embeddings = []

# In-memory latest frame store (note: for production use a shared store like Redis)
latest_frame = None
latest_frame_lock = Lock()
latest_frame_time = None

def init_camera():
    global vs
    print("[INFO] starting video stream...")
    vs = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    vs.set(cv2.CAP_PROP_FPS, 60)
    vs.set(cv2.CAP_PROP_BUFFERSIZE, 0)
    vs.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    vs.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    #address = "http://192.168.66.190:8080/video"
    #address = "http://10.19.27.3:8080/video"
    #vs.open(address)
    if not vs.isOpened():
        print("Cannot open camera")
        exit()
    time.sleep(2.0)

def load_known_embeddings():
    known_embeddings = []
    if not os.path.exists(Config.KNOWN_FACES_DIR):
        print(f"[WARNING] {Config.KNOWN_FACES_DIR} directory not found!")
        return known_embeddings
    for person_dir in os.listdir(Config.KNOWN_FACES_DIR):
        person_path = os.path.join(Config.KNOWN_FACES_DIR, person_dir)
        if os.path.isdir(person_path):
            for img_file in os.listdir(person_path):
                if img_file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    img_path = os.path.join(person_path, img_file)
                    try:
                        emb = DeepFace.represent(img_path, 
                                                 model_name=Config.MODEL_NAME, 
                                                 enforce_detection=False,
                                                 detector_backend='opencv')
                        if emb:
                            known_embeddings.append((person_dir, np.array(emb[0]['embedding'])))
                    except Exception as e:
                        print(f"[WARNING] Failed to compute embedding for {img_path}: {e}")
    print(f"[INFO] Loaded {len(known_embeddings)} known face embeddings")
    return known_embeddings

def cosine_distance(a, b):
    a_norm = a / np.linalg.norm(a)
    b_norm = b / np.linalg.norm(b)
    return 1 - np.dot(a_norm, b_norm)

def recognize_face(face_image, known_embeddings):
    try:
        face_rgb = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
        emb_list = DeepFace.represent(face_rgb, 
                                      model_name=Config.MODEL_NAME, 
                                      enforce_detection=False,
                                      detector_backend='skip')
        if not emb_list:
            return Config.UNKNOWN_LABEL, None
        face_emb = np.array(emb_list[0]['embedding'])
        if not known_embeddings:
            return Config.UNKNOWN_LABEL, None
        best_match = None
        best_distance = float('inf')
        for person_name, emb in known_embeddings:
            dist = cosine_distance(face_emb, emb)
            if dist < best_distance:
                best_distance = dist
                best_match = person_name
        print(f"[DEBUG] Best distance: {best_distance:.4f} (threshold: {Config.RECOGNITION_THRESHOLD})")
        if best_match and best_distance < Config.RECOGNITION_THRESHOLD:
            return best_match, best_distance
        return Config.UNKNOWN_LABEL, best_distance
    except Exception as e:
        print(f"[ERROR] Face recognition failed: {e}")
        return Config.UNKNOWN_LABEL, None

def perform_recognized_action(person_name):
    print(f"[ACTION] Welcome {person_name}!")
    new_notification = Notification(
        person_name=person_name,
        status='accepted',
        confidence=0.95,  # Example confidence
        image_url='https://placehold.co/400',
        timestamp=datetime.utcnow()
    )
    db.session.add(new_notification)
    db.session.commit()
    if Config.EMAIL_ENABLED:
        send_email(Config.MAILERO_SENDER, "Known Person Detected", f"Welcome {person_name}!")
    if Config.PUSH_ENABLED:
        send_push_notification(f"Known person detected: {person_name}")

def perform_unknown_action():
    print("[ACTION] Unknown person detected!")
    new_notification = Notification(
        person_name=Config.UNKNOWN_LABEL,
        status='rejected',
        confidence=0.32,  # Example confidence
        image_url='https://placehold.co/400',
        timestamp=datetime.utcnow()
    )
    db.session.add(new_notification)
    db.session.commit()
    if Config.EMAIL_ENABLED:
        send_email(Config.MAILERO_SENDER, "Unknown Person Detected", "An unknown person was detected at the door.")
    if Config.PUSH_ENABLED:
        send_push_notification("Unknown person detected at the door.")
    if Config.CALL_ENABLED:
        initiate_call()

def gen_frames():
    global frame_counter, recognized_faces, last_action_time
    while streaming:
        ret, frame = vs.read()
        if not ret or frame is None:
            continue
        frame = imutils.resize(frame, width=600)
        (h, w) = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0,
                                     (300, 300), (104.0, 177.0, 123.0))
        detector.setInput(blob)
        detections = detector.forward()
        frame_counter += 1
        do_recognition = (frame_counter % FRAME_SKIP == 0)
        for i in range(0, detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence < Config.CONFIDENCE_THRESHOLD:
                continue
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (startX, startY, endX, endY) = box.astype("int")
            startX, startY = max(0, startX), max(0, startY)
            endX, endY = min(w, endX), min(h, endY)
            face_roi = frame[startY:endY, startX:endX]
            if face_roi.size == 0:
                continue
            if do_recognition:
                person_name, distance = recognize_face(face_roi, known_embeddings)
            else:
                person_name = recognized_faces.get(i, Config.UNKNOWN_LABEL)
                distance = None
            if person_name == Config.UNKNOWN_LABEL:
                label = Config.UNKNOWN_LABEL
                color = (0, 0, 255)
                current_time = time.time()
                if i not in last_action_time or current_time - last_action_time.get(i, 0) > 5:
                    #perform_unknown_action()
                    last_action_time[i] = current_time
            else:
                label = f"{person_name} ({distance:.3f})" if distance is not None else person_name
                color = (0, 255, 0)
                current_time = time.time()
                if recognized_faces.get(i) != person_name or current_time - last_action_time.get(i, 0) > 10:
                    #perform_recognized_action(person_name)
                    last_action_time[i] = current_time
            recognized_faces[i] = person_name
            text = f"{label} {confidence*100:.1f}%"
            y = startY - 10 if startY - 10 > 10 else startY + 10
            cv2.rectangle(frame, (startX, startY), (endX, endY), color, 2)
            cv2.putText(frame, text, (startX, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

known_embeddings = None # load_known_embeddings()

@video_bp.route('/stream', methods=['GET'])
def video_stream():
    global streaming, known_embeddings
    if not streaming:
        return jsonify({'error': 'Streaming not started'}), 400
    init_camera()
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@video_bp.route('/start', methods=['POST'])
@jwt_required()
def start_stream():
    global streaming, known_embeddings
    if streaming:
        return jsonify({'message': 'Stream already running'}), 200
    #known_embeddings = load_known_embeddings()
    init_camera()
    streaming = True
    return jsonify({'message': 'Stream started'}), 200

@video_bp.route('/stop', methods=['POST'])
@jwt_required()
def stop_stream():
    global streaming, vs
    if not streaming:
        return jsonify({'message': 'Stream not running'}), 200
    streaming = False
    if vs:
        vs.release()
    return jsonify({'message': 'Stream stopped'}), 200

@video_bp.route('/get', methods=['GET'])
#@jwt_required()
def stream_state():
    global streaming
    return jsonify({'message': streaming}), 200

@video_bp.route('/update-state', methods=['POST', 'GET'])
#@jwt_required()
def update_stream():
    global streaming, vs
    state = request.form.get('update')
    if state:
        if not streaming:
            init_camera()
            streaming = True
            return jsonify({'message': 'Stream up and running'}), 200
        else:
            vs.release()
            streaming = False
            return jsonify({'message': 'Stream stopped'}), 200


    # Image upload endpoint: stores uploaded image to Supabase storage under users/<user_id>/
    @video_bp.route('/upload_image', methods=['POST'])
    @jwt_required()
    def upload_user_image():
        user = get_jwt_identity()
        user_id = user.get('id') if isinstance(user, dict) else str(user)
        if 'file' not in request.files:
            return jsonify({'error': 'no file provided'}), 400
        file = request.files['file']
        filename = secure_filename(file.filename)
        if filename == '':
            return jsonify({'error': 'invalid filename'}), 400
        path = f"users/{user_id}/{filename}"
        file_bytes = file.read()
        try:
            res = upload_image('images', path, file_bytes, content_type=file.mimetype)
            return jsonify({'status': 'ok', 'result': res}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500


    @video_bp.route('/list_images/<user_id>', methods=['GET'])
    @jwt_required()
    def list_images(user_id):
        try:
            urls = list_user_images('images', f"users/{user_id}/")
            return jsonify({'status': 'ok', 'images': urls}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500


    # Endpoint for Raspberry Pi (or any client) to POST frames; frontend can poll GET /frame to retrieve latest
    @video_bp.route('/frame', methods=['POST'])
    def post_frame():
        global latest_frame, latest_frame_time
        if 'frame' not in request.files:
            return jsonify({'error': 'no frame provided'}), 400
        file = request.files['frame']
        img_bytes = file.read()
        with latest_frame_lock:
            latest_frame = img_bytes
            latest_frame_time = datetime.utcnow().isoformat()
        return jsonify({'status': 'ok', 'timestamp': latest_frame_time}), 200


    @video_bp.route('/frame', methods=['GET'])
    def get_frame():
        global latest_frame, latest_frame_time
        with latest_frame_lock:
            if not latest_frame:
                return jsonify({'available': False}), 404
            buf = io.BytesIO(latest_frame)
            # return raw jpeg
            return send_file(buf, mimetype='image/jpeg', as_attachment=False, download_name='frame.jpg') """