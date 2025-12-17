from flask import Blueprint, json, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, WatchlistMember, FaceImage, Device
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import uuid
from supabase_client import (
    upload_watchlist_image, 
    get_watchlist_images_for_device,
    delete_watchlist_image,
    get_public_url
)

watchlist_bp = Blueprint('watchlist', __name__)

# Configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@watchlist_bp.route('', methods=['GET'])
@jwt_required()
def get_watchlist():
    """Get all watchlist members for the current user"""
    user_identity_raw = get_jwt_identity()
    user_identity = json.loads(user_identity_raw)
    user_id = user_identity['id']
    
    # Get user's device
    device = Device.query.filter_by(owner_id=uuid.UUID(user_id)).first()
    if not device:
        return jsonify({"error": "No device found for user"}), 404
    
    device_id = str(device.id)
    
    members = WatchlistMember.query.filter_by(user_id=user_id).all()
    
    return jsonify([{
        "id": str(m.id),
        "name": m.name,
        "status": m.status,
        "imagesCount": len(m.images),
        "addedDate": m.added_at.isoformat() if m.added_at else None,
        "images": [{
            "id": str(img.id),
            "url": get_face_image_url(img, device_id),
            "filename": img.filename,
            "uploadDate": img.uploaded_at.isoformat() if img.uploaded_at else None
        } for img in m.images]
    } for m in members]), 200

def get_face_image_url(face_image, device_id):
    """Get URL for face image from Supabase"""
    if face_image.supabase_path:
        try:
            return get_public_url('images', face_image.supabase_path)
        except:
            pass
    
    # Fallback to old path if available
    if face_image.path:
        return f"/static/known_faces/{face_image.path}"
    
    return ""

@watchlist_bp.route('/<member_id>', methods=['GET'])
@jwt_required()
def get_single_watchlist_member(member_id):
    """Get a single watchlist member"""
    user_identity_raw = get_jwt_identity()
    user_identity = json.loads(user_identity_raw)
    user_id = user_identity['id']
    
    try:
        member_uuid = uuid.UUID(member_id)
    except ValueError:
        return jsonify({"msg": "Invalid member ID format"}), 400

    member = WatchlistMember.query.filter_by(id=member_uuid, user_id=user_id).first_or_404()
    
    # Get user's device
    device = Device.query.filter_by(owner_id=user_id).first()
    device_id = str(device.id) if device else "unknown"

    return jsonify({
        "id": str(member.id),
        "name": member.name,
        "status": member.status,
        "imagesCount": len(member.images),
        "addedDate": member.added_at.isoformat() if member.added_at else None,
        "images": [{
            "id": str(img.id),
            "url": get_face_image_url(img, device_id),
            "filename": img.filename,
            "uploadDate": img.uploaded_at.isoformat() if img.uploaded_at else None
        } for img in member.images]
    }), 200

@watchlist_bp.route('', methods=['POST'])
@jwt_required()
def add_watchlist_member():
    """Add a new watchlist member"""
    user_identity_raw = get_jwt_identity()
    user_identity = json.loads(user_identity_raw)
    user_id = user_identity['id']
    data = request.get_json()
    
    if 'name' not in data:
        return jsonify({"error": "Name is required"}), 400

    name = data.get('name', '').strip()
    status = data.get('status', 'active')
    
    if not name:
        return jsonify({"error": "Name cannot be empty"}), 400

    # Validate status
    if status not in ['active', 'inactive']:
        return jsonify({"error": "Status must be 'active' or 'inactive'"}), 400

    member = WatchlistMember(
        id=uuid.uuid4(),
        user_id=user_id,
        name=name,
        status=status
    )
    db.session.add(member)
    db.session.commit()

    return jsonify({
        "message": "Member added to watchlist",
        "member": {
            "id": str(member.id),
            "name": member.name,
            "status": member.status,
            "addedDate": member.added_at.isoformat() if member.added_at else None,
        }
    }), 201

@watchlist_bp.route('/<member_id>', methods=['PUT'])
@jwt_required()
def update_watchlist_member(member_id):
    """Update a watchlist member"""
    user_identity_raw = get_jwt_identity()
    user_identity = json.loads(user_identity_raw)
    user_id = user_identity['id']
    
    try:
        member_uuid = uuid.UUID(member_id)
    except ValueError:
        return jsonify({"error": "Invalid member ID format"}), 400
    
    member = WatchlistMember.query.filter_by(id=member_uuid, user_id=user_id).first_or_404()
    data = request.get_json() or {}

    if 'name' in data:
        new_name = data['name'].strip()
        if new_name:
            member.name = new_name
    
    if 'status' in data:
        if data['status'] not in ['active', 'inactive']:
            return jsonify({"error": "Status must be 'active' or 'inactive'"}), 400
        member.status = data['status']

    db.session.commit()

    return jsonify({
        "message": "Member updated",
        "member": {
            "id": str(member.id),
            "name": member.name,
            "status": member.status,
            "imagesCount": len(member.images)
        }
    }), 200

@watchlist_bp.route('/<member_id>', methods=['DELETE'])
@jwt_required()
def delete_watchlist_member(member_id):
    """Delete a watchlist member and their images"""
    user_identity_raw = get_jwt_identity()
    user_identity = json.loads(user_identity_raw)
    user_id = user_identity['id']
    
    try:
        member_uuid = uuid.UUID(member_id)
    except ValueError:
        return jsonify({"error": "Invalid member ID format"}), 400
    
    member = WatchlistMember.query.filter_by(id=member_uuid, user_id=user_id).first_or_404()
    
    # Get user's device
    device = Device.query.filter_by(owner_id=user_id).first()
    if device:
        device_id = str(device.id)
        
        # Delete images from Supabase
        for image in member.images:
            if image.supabase_path:
                delete_watchlist_image(device_id, image.supabase_path)
    
    # Delete from database
    db.session.delete(member)
    db.session.commit()

    return jsonify({"message": "Member removed from watchlist"}), 200

@watchlist_bp.route('/<member_id>/images', methods=['POST'])
@jwt_required()
def upload_images_to_member(member_id):
    """Upload images to a watchlist member"""
    user_identity_raw = get_jwt_identity()
    user_identity = json.loads(user_identity_raw)
    user_id = user_identity['id']
    
    try:
        member_uuid = uuid.UUID(member_id)
    except ValueError:
        return jsonify({"error": "Invalid member ID format"}), 400
    
    member = WatchlistMember.query.filter_by(id=member_uuid, user_id=user_id).first_or_404()
    
    if 'images' not in request.files:
        return jsonify({"error": "No images provided"}), 400

    files = request.files.getlist('images')
    uploaded = []
    
    # Get user's device
    device = Device.query.filter_by(owner_id=user_id).first()
    if not device:
        return jsonify({"error": "No device found for user"}), 404
    
    device_id = str(device.id)
    
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            try:
                # Read file bytes
                file_bytes = file.read()
                
                # Upload to Supabase
                upload_result = upload_watchlist_image(
                    user_id=user_id,
                    device_id=device_id,
                    watchlist_id=str(member.id),
                    watchlist_name=member.name,
                    file_bytes=file_bytes,
                    filename=secure_filename(file.filename),
                    content_type=file.mimetype
                )
                
                if upload_result.get('success'):
                    # Create FaceImage record
                    img = FaceImage(
                        id=uuid.uuid4(),
                        member_id=member.id,
                        filename=secure_filename(file.filename),
                        supabase_path=upload_result.get('path'),
                        path=upload_result.get('public_url') or upload_result.get('signed_url', '')
                    )
                    db.session.add(img)
                    
                    uploaded.append({
                        "id": str(img.id),
                        "url": upload_result.get('public_url') or upload_result.get('signed_url', ''),
                        "filename": img.filename,
                        "uploadDate": img.uploaded_at.isoformat() if img.uploaded_at else None
                    })
                else:
                    print(f"[ERROR] Failed to upload image: {upload_result.get('error')}")
                    
            except Exception as e:
                print(f"[ERROR] Error uploading image: {e}")
                continue

    db.session.commit()

    return jsonify({
        "message": f"{len(uploaded)} image(s) uploaded",
        "images": uploaded
    }), 201

@watchlist_bp.route('/images/<image_id>', methods=['DELETE'])
@jwt_required()
def delete_image(image_id):
    """Delete a specific image"""
    user_identity_raw = get_jwt_identity()
    user_identity = json.loads(user_identity_raw)
    user_id = user_identity['id']
    
    try:
        image_uuid = uuid.UUID(image_id)
    except ValueError:
        return jsonify({"error": "Invalid image ID format"}), 400
    
    # Find image belonging to user
    image = FaceImage.query.join(WatchlistMember).filter(
        FaceImage.id == image_uuid,
        WatchlistMember.user_id == user_id
    ).first_or_404()
    
    # Get user's device
    device = Device.query.filter_by(owner_id=user_id).first()
    if device and image.supabase_path:
        device_id = str(device.id)
        delete_watchlist_image(device_id, image.supabase_path)
    
    db.session.delete(image)
    db.session.commit()

    return jsonify({"message": "Image deleted"}), 200

@watchlist_bp.route('/sync-images', methods=['POST'])
@jwt_required()
def sync_watchlist_images():
    """Sync watchlist images from Supabase to local database"""
    user_identity_raw = get_jwt_identity()
    user_identity = json.loads(user_identity_raw)
    user_id = user_identity['id']
    
    # Get user's device
    device = Device.query.filter_by(owner_id=user_id).first()
    if not device:
        return jsonify({"error": "No device found for user"}), 404
    
    device_id = str(device.id)
    
    # Get all images from Supabase for this device
    supabase_images = get_watchlist_images_for_device(device_id)
    
    # Get all watchlist members for user
    members = WatchlistMember.query.filter_by(user_id=user_id).all()
    
    synced_count = 0
    for supabase_image in supabase_images:
        # Extract watchlist ID from filename
        # Format: deviceID/watchlistId_watchlistName.ext
        filename = supabase_image['filename']
        
        # Try to extract watchlist ID (first part before underscore)
        if '_' in filename:
            watchlist_part = filename.split('_')[0]
            
            # Find matching watchlist member
            for member in members:
                if str(member.id) == watchlist_part:
                    # Check if image already exists
                    existing_image = FaceImage.query.filter_by(
                        supabase_path=supabase_image['path']
                    ).first()
                    
                    if not existing_image:
                        # Create new FaceImage record
                        img = FaceImage(
                            id=uuid.uuid4(),
                            member_id=member.id,
                            filename=filename,
                            supabase_path=supabase_image['path'],
                            path=supabase_image['url']
                        )
                        db.session.add(img)
                        synced_count += 1
                    break
    
    db.session.commit()
    
    return jsonify({
        "message": f"Synced {synced_count} images from Supabase",
        "synced_count": synced_count
    }), 200