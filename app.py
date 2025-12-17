import eventlet
eventlet.monkey_patch()

from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_migrate import Migrate
from flask_socketio import SocketIO

from config import Config
from models import db
from blueprints.auth import auth_bp
from blueprints.users import users_bp
from blueprints.notifications import notifications_bp
from blueprints.video import video_bp
from blueprints.door import door_bp
from blueprints.watchlist import watchlist_bp
from blueprints.images import images_bp
from blueprints.video_ws import VideoStreamNamespace


socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode="eventlet",
    max_http_buffer_size=20 * 1024 * 1024,  # 20MB (video frames)
    ping_interval=25,
    ping_timeout=60
)

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
socketio.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)
CORS(app, supports_credentials=True)

# JWT error handlers
@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({"error": "Missing Authorization Header"}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({"error": "Invalid token"}), 422

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({"error": "Token has expired"}), 401

# Register REST blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(users_bp, url_prefix='/api/users')
app.register_blueprint(watchlist_bp, url_prefix='/api/watchlist')
app.register_blueprint(notifications_bp, url_prefix='/api/notifications')
app.register_blueprint(video_bp, url_prefix='/api/video')
app.register_blueprint(door_bp, url_prefix='/api/door')
app.register_blueprint(images_bp, url_prefix='/api/images')

# Register WebSocket namespace
socketio.on_namespace(VideoStreamNamespace("/ws/video"))

# DB init
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False  # REQUIRED for eventlet
    )
