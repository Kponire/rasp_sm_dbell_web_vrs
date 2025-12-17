import json
import uuid
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, DoorLock, Device
from datetime import datetime

door_bp = Blueprint('door', __name__)

@door_bp.route('/state', methods=['GET'])
@jwt_required()
def get_door_state():
    """Get door state for user's device"""
    user_identity_raw = get_jwt_identity()
    user_identity = json.loads(user_identity_raw)
    user_id = user_identity['id']
    
    # Get user's device
    device = Device.query.filter_by(owner_id=user_id).first()
    if not device:
        return jsonify({'error': 'No device found for user'}), 404
    
    # Get door lock for this device/user
    door = DoorLock.query.filter_by(device_id=device.id).first()
    if not door:
        # Create default door lock
        door = DoorLock(
            device_id=device.id,
            user_id=user_id,
            state='locked'
        )
        db.session.add(door)
        db.session.commit()
    
    return jsonify({
        'state': door.state,
        'device_id': str(device.id),
        'device_name': device.name,
        'last_updated': door.last_updated.isoformat()
    }), 200

@door_bp.route('/state/device/<device_id>', methods=['GET'])
def get_door_state_by_device(device_id):
    """Get door state by device ID (used by Raspberry Pi)"""
    try:
        device_id = uuid.UUID(device_id)
    except ValueError:
        return jsonify({"error": "Invalid device ID format"}), 400
    
    door = DoorLock.query.filter_by(device_id=device_id).first()
    if not door:
        return jsonify({
            'state': 'locked',
            'device_id': device_id,
            'last_updated': datetime.utcnow().isoformat()
        }), 200
    
    return jsonify({
        'state': door.state,
        'device_id': str(door.device_id),
        'last_updated': door.last_updated.isoformat()
    }), 200

@door_bp.route('/state', methods=['PUT'])
@jwt_required()
def update_door_state():
    """Update door state for user's device"""
    user_identity_raw = get_jwt_identity()
    user_identity = json.loads(user_identity_raw)
    user_id = user_identity['id']
    data = request.get_json()
    new_state = data.get('state')  # 'locked' or 'unlocked'
    
    if new_state not in ['locked', 'unlocked']:
        return jsonify({'error': 'Invalid state'}), 400
    
    # Get user's device
    device = Device.query.filter_by(owner_id=user_id).first()
    if not device:
        return jsonify({'error': 'No device found for user'}), 404
    
    # Find or create door lock
    door = DoorLock.query.filter_by(device_id=device.id).first()
    if not door:
        door = DoorLock(
            device_id=device.id,
            user_id=user_id,
            state=new_state
        )
    else:
        door.state = new_state
    
    door.last_updated = datetime.utcnow()
    db.session.add(door)
    db.session.commit()
    
    return jsonify({
        'message': 'Door state updated',
        'state': door.state,
        'device_id': str(device.id),
        'device_name': device.name,
        'last_updated': door.last_updated.isoformat()
    }), 200

@door_bp.route('/state/device/<device_id>', methods=['PUT'])
def update_door_state_by_device(device_id):
    """Update door state by device ID (used by Raspberry Pi)"""
    data = request.get_json()
    new_state = data.get('state')
    
    if new_state not in ['locked', 'unlocked']:
        return jsonify({'error': 'Invalid state'}), 400
    
    try:
        device_id = uuid.UUID(device_id)
    except ValueError:
        return jsonify({"error": "Invalid device ID format"}), 400
    
    door = DoorLock.query.filter_by(device_id=device_id).first()
    if not door:
        # Create new door lock entry
        door = DoorLock(
            device_id=device_id,
            state=new_state
        )
    else:
        door.state = new_state
    
    door.last_updated = datetime.utcnow()
    db.session.add(door)
    db.session.commit()
    
    return jsonify({
        'message': 'Door state updated',
        'state': door.state,
        'device_id': device_id,
        'last_updated': door.last_updated.isoformat()
    }), 200