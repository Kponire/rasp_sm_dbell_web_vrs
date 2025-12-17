from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from blueprints.auth import auth_bp
from blueprints.users import users_bp
from blueprints.notifications import notifications_bp
from blueprints.video import video_bp
from blueprints.door import door_bp
from blueprints.watchlist import watchlist_bp
from blueprints.images import images_bp
from config import Config
from datetime import datetime
from models import db
from flask_cors import CORS
from flask_migrate import Migrate

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate = Migrate(app, db, directory="migrations")
jwt = JWTManager(app)
CORS(app, supports_credentials=True, expose_headers=["Authorization"])

@jwt.unauthorized_loader
def missing_token_callback(error):
    print("MISSING TOKEN:", error)
    return jsonify({"error": "Missing Authorization Header"}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    print("INVALID TOKEN:", error)
    return jsonify({"error": "Invalid token"}), 422

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    print("EXPIRED TOKEN")
    return jsonify({"error": "Token has expired"}), 401

@jwt.revoked_token_loader
def revoked_token_callback(jwt_header, jwt_payload):
    print("REVOKED TOKEN")
    return jsonify({"error": "Token has been revoked"}), 401

@jwt.needs_fresh_token_loader
def needs_fresh_token_callback(jwt_header, jwt_payload):
    print("FRESH TOKEN REQUIRED")
    return jsonify({"error": "Fresh token required"}), 401

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(users_bp, url_prefix='/api/users')
app.register_blueprint(watchlist_bp, url_prefix='/api/watchlist')
app.register_blueprint(notifications_bp, url_prefix='/api/notifications')
app.register_blueprint(video_bp, url_prefix='/api/video')
app.register_blueprint(door_bp, url_prefix='/api/door')
app.register_blueprint(images_bp, url_prefix='/api/images')


# Initialize database
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)