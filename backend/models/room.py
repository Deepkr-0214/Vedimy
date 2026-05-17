from extensions import db
import uuid
from datetime import datetime

class Room(db.Model):
    __tablename__ = 'rooms'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    host_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    room_type = db.Column(db.String(20), default='meeting')
    status = db.Column(db.String(20), default='scheduled') # scheduled, active, paused, ended
    is_active = db.Column(db.Boolean, default=True)
    is_locked = db.Column(db.Boolean, default=False)
    waiting_room_enabled = db.Column(db.Boolean, default=False)
    password_hash = db.Column(db.String(255))
    max_participants = db.Column(db.Integer, default=50)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)
    security_flags_json = db.Column(db.Text, default='{}')

class RoomParticipant(db.Model):
    __tablename__ = 'room_participants'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = db.Column(db.String(36), db.ForeignKey('rooms.id'))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    status = db.Column(db.String(20), default='joined') # waiting, approved, rejected, joined
    join_time = db.Column(db.DateTime, default=datetime.utcnow)
    leave_time = db.Column(db.DateTime)
    face_verified = db.Column(db.Boolean, default=False)
    peer_id = db.Column(db.String(255))
