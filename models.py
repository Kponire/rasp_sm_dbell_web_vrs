from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from datetime import datetime
import uuid

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    role = db.Column(db.String(20), default='user')
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    # Relationships
    watchlist = db.relationship('WatchlistMember', backref='user', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user')
    door_lock = db.relationship('DoorLock', backref='user', uselist=False)
    devices = db.relationship('Device', backref='owner')


class Device(db.Model):
    __tablename__ = 'device'

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid()
    )

    serial_number = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), default="My Doorbell")
    is_online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime(timezone=True))

    created_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now()
    )

    owner_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('user.id'),
        nullable=False
    )


class WatchlistMember(db.Model):
    __tablename__ = 'watchlist_member'

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid()
    )

    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('user.id'),
        nullable=False
    )

    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='active')

    added_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now()
    )

    images = db.relationship(
        'FaceImage',
        backref='member',
        cascade='all, delete-orphan'
    )


class FaceImage(db.Model):
    __tablename__ = 'face_image'

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid()
    )

    member_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('watchlist_member.id'),
        nullable=False
    )

    path = db.Column(db.String(500), nullable=True)
    supabase_path = db.Column(db.String(500), nullable=True)
    filename = db.Column(db.String(100), nullable=False)

    uploaded_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now()
    )


class Notification(db.Model):
    __tablename__ = 'notification'

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid()
    )

    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('user.id'),
        nullable=False
    )

    person_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    confidence = db.Column(db.Float)
    image_path = db.Column(db.String(255))

    timestamp = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now()
    )


class DoorLock(db.Model):
    __tablename__ = 'door_lock'
    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid()
    )
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('user.id'),
        nullable=True
    )
    device_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('device.id'),
        nullable=False,
        unique=True
    )
    state = db.Column(db.String(20), default='locked')
    last_updated = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now()
    )
    
    # Relationships
    device = db.relationship('Device', backref='door_lock')
