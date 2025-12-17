from flask import Blueprint, json, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from web_backend.models import WatchlistMember, db, User
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    phone = data.get('phone')
    
    if not all([name, email, password, phone]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    try:
        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, password=hashed_password, phone=phone, created_at=datetime.utcnow())
        db.session.add(new_user)
        db.session.flush()

        owner_member = WatchlistMember(
            user_id=new_user.id,
            name=f"{new_user.name} (Me)",
            status='active',
            added_at=datetime.utcnow()
        )
        db.session.add(owner_member)
        db.session.commit()
        
        return jsonify({'message': 'User registered successfully', 'user_id': new_user.id}), 201
    except Exception as e:
        db.session.rollback()
        print(f"Database error during registration: {e}") 
        return jsonify({'error': 'An internal error occurred during registration'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({'error': 'Invalid credentials'}), 401
    user_identity = json.dumps({
        'id': user.id,
        'email': user.email,
        'role': user.role,
        'name': user.name
    })
    access_token = create_access_token(identity=user_identity)
    return jsonify({'access_token': access_token, 'user': {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role
    }}), 200

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'status': user.status,
        'role': user.role,
        'created_at': user.created_at.isoformat()
    }), 200