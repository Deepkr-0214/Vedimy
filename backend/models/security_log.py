from extensions import db
import uuid
from datetime import datetime

class SecurityLog(db.Model):
    __tablename__ = 'security_logs'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    room_id = db.Column(db.String(36), db.ForeignKey('rooms.id'), nullable=True)
    event_type = db.Column(db.String(50), nullable=False)
    details = db.Column(db.JSON, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
