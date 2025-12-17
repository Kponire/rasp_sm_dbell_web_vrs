import json
import uuid
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash
from web_backend.models import db, User, FaceImage
from datetime import datetime
import os
from pathlib import Path
from werkzeug.security import check_password_hash

users_bp = Blueprint('users', __name__)

@users_bp.route('', methods=['GET'])
@jwt_required()
def get_users():
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'name': u.name,
        'email': u.email,
        'status': u.status,
        'createdAt': u.created_at.isoformat(),
        'role': u.role,
        "watchlistCount": len(u.watchlist)
    } for u in users]), 200

@users_bp.route('/<user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    try:
        user_id = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"error": "Invalid user ID format"}), 400
    user = User.query.get_or_404(user_id)
    return jsonify({
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "status": user.status,
        "role": user.role,
        "createdAt": user.created_at.isoformat(),
        "watchlistCount": len(user.watchlist)
    }), 200

@users_bp.route('/<user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    user_identity_raw = get_jwt_identity()
    user_identity = json.loads(user_identity_raw)
    current_user = user_identity['id']
    
    try:
        user_id = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"error": "Invalid user ID format"}), 400
    
    user = User.query.get_or_404(user_id)
    if user.id != current_user: # and user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    user.name = data.get('name', user.name)
    user.email = data.get('email', user.email)
    if data.get('password'):
        user.password = generate_password_hash(data['password'])
    #user.status = data.get('status', user.status)
    #user.role = data.get('role', user.role)
    db.session.commit()
    return jsonify({'message': 'User updated successfully'}), 200

@users_bp.route('/<user_id>/deactivate', methods=['POST'])
@jwt_required()
def deactivate_user(user_id):
    try:
        user_id = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"error": "Invalid user ID format"}), 400
    user = User.query.get_or_404(user_id)
    user.status = 'inactive'
    db.session.commit()
    return jsonify({'message': 'User deactivated'}), 200

@users_bp.route('/<user_id>/images', methods=['POST'])
@jwt_required()
def upload_image(user_id):
    try:
        user_id = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"error": "Invalid user ID format"}), 400
    user = User.query.get_or_404(user_id)
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        return jsonify({'error': 'Invalid file format'}), 400
    
    # Save file to known_faces/<user_name>/
    user_dir = Path(f"known_faces/{user.name}")
    user_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_dir / file.filename
    file.save(file_path)
    
    # Add to database
    new_image = FaceImage(
        user_id=user.id,
        url=str(file_path),
        name=file.filename,
        upload_date=datetime.utcnow()
    )
    db.session.add(new_image)
    db.session.commit()
    
    return jsonify({
        'id': new_image.id,
        'url': str(new_image.url),
        'name': new_image.name,
        'uploadDate': new_image.upload_date.isoformat()
    }), 201

@users_bp.route('/me/password', methods=['PUT'])
@jwt_required()
def change_password():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({"error": "Both passwords are required"}), 400

    if not check_password_hash(user.password, current_password):
        return jsonify({"error": "Current password is incorrect"}), 401

    user.password = generate_password_hash(new_password)
    db.session.commit()

    return jsonify({"message": "Password changed successfully"}), 200