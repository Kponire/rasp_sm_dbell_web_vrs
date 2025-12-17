from flask import Blueprint, json, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import base64
import uuid
from datetime import datetime
from web_backend.supabase_client import upload_captured_face

images_bp = Blueprint('images', __name__)

@images_bp.route('/upload-captured', methods=['POST'])
def upload_captured_image():
    """Upload captured face image to Supabase captured-faces bucket"""
    data = request.get_json()
    
    # Required fields
    device_id = data.get('deviceId')
    image_data = data.get('imageData')
    filename = data.get('filename')
    
    if not all([device_id, image_data, filename]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        # Decode base64 image
        image_bytes = base64.b64decode(image_data)
        
        # Get additional data
        person_name = data.get('personName', 'Unknown')
        status = data.get('status', 'unrecognized')
        bucket = data.get('bucket', 'captured-faces')
        
        # Upload to Supabase
        upload_result = upload_captured_face(
            device_id=device_id,
            person_name=person_name,
            status=status,
            file_bytes=image_bytes,
            filename=filename
        )
        
        if upload_result.get('success'):
            return jsonify({
                'message': 'Image uploaded successfully',
                'url': upload_result.get('public_url') or upload_result.get('signed_url', ''),
                'path': upload_result.get('path'),
                'bucket': bucket
            }), 200
        else:
            return jsonify({'error': 'Failed to upload to Supabase'}), 500
            
    except Exception as e:
        print(f"[ERROR] Failed to upload captured image: {e}")
        return jsonify({'error': str(e)}), 500

@images_bp.route('/captured/<device_id>', methods=['GET'])
@jwt_required()
def get_captured_images(device_id):
    """Get captured images for a device"""
    user_identity_raw = get_jwt_identity()
    user_identity = json.loads(user_identity_raw)
    user_id = user_identity['id']
    
    # Verify user owns the device
    from web_backend.models import Device
    try:
        device_id = uuid.UUID(device_id)
    except ValueError:
        return jsonify({"error": "Invalid device ID format"}), 400
    
    device = Device.query.filter_by(id=device_id, owner_id=user_id).first()
    if not device:
        return jsonify({'error': 'Device not found or unauthorized'}), 404
    
    # Get images from Supabase
    from web_backend.supabase_client import list_files_in_bucket
    files = list_files_in_bucket('captured-faces', device_id)
    
    images = []
    for file_info in files:
        if file_info.get('name'):
            # Parse filename for metadata
            filename = file_info['name'].split('/')[-1] if '/' in file_info['name'] else file_info['name']
            parts = filename.replace('.jpg', '').split('_')
            
            person_name = "Unknown"
            status = "unrecognized"
            timestamp = ""
            
            if len(parts) >= 3:
                person_name = parts[0].replace('_', ' ')
                status = parts[1]
                timestamp = parts[2] if len(parts) > 2 else ""
            
            images.append({
                'filename': filename,
                'path': file_info['name'],
                'person_name': person_name,
                'status': status,
                'timestamp': timestamp,
                'size': file_info.get('metadata', {}).get('size'),
                'created_at': file_info.get('created_at')
            })
    
    return jsonify({
        'device_id': device_id,
        'device_name': device.name,
        'images': images,
        'count': len(images)
    }), 200