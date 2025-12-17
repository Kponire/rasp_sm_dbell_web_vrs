from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from web_backend.models import db, Device, User
from datetime import datetime
import uuid

device_bp = Blueprint('device', __name__)

@device_bp.route('/register', methods=['POST'])
def register_device():
    """Register a new device"""
    data = request.get_json()
    device_id = data.get('deviceId')
    device_name = data.get('deviceName', 'My Doorbell')
    
    if not device_id:
        return jsonify({'error': 'deviceId required'}), 400
    
    # Check if device already exists
    device = Device.query.filter_by(serial_number=device_id).first()
    
    if not device:
        # Create new device (without owner for now)
        device = Device(
            id=uuid.uuid4(),
            serial_number=device_id,
            name=device_name,
            is_online=True,
            last_seen=datetime.utcnow()
        )
        db.session.add(device)
    else:
        # Update existing device
        device.is_online = True
        device.last_seen = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'message': 'Device registered',
        'deviceId': device.serial_number,
        'deviceName': device.name,
        'is_online': device.is_online
    }), 200

@device_bp.route('/assign', methods=['POST'])
@jwt_required()
def assign_device_to_user():
    """Assign a device to the current user"""
    user_id = get_jwt_identity()
    data = request.get_json()
    device_id = data.get('deviceId')
    
    if not device_id:
        return jsonify({'error': 'deviceId required'}), 400
    
    # Find device
    device = Device.query.filter_by(serial_number=device_id).first()
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    
    # Check if device is already assigned to another user
    if device.owner_id and str(device.owner_id) != user_id:
        return jsonify({'error': 'Device already assigned to another user'}), 403
    
    # Assign to current user
    device.owner_id = user_id
    device.is_online = True
    device.last_seen = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'message': 'Device assigned to user',
        'deviceId': device.serial_number,
        'deviceName': device.name,
        'owner_id': user_id
    }), 200

@device_bp.route('/my-devices', methods=['GET'])
@jwt_required()
def get_user_devices():
    """Get all devices for current user"""
    user_id = get_jwt_identity()
    
    devices = Device.query.filter_by(owner_id=user_id).all()
    
    return jsonify([{
        'id': str(device.id),
        'serial_number': device.serial_number,
        'name': device.name,
        'is_online': device.is_online,
        'last_seen': device.last_seen.isoformat() if device.last_seen else None
    } for device in devices]), 200