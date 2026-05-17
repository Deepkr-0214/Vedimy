from extensions import db
import uuid
from datetime import datetime

class AuthHistory(db.Model):
    __tablename__ = 'auth_history'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    auth_method = db.Column(db.String(20), default='password') # 'password', 'face'
    status = db.Column(db.String(20), default='success')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
