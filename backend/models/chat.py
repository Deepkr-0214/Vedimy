from extensions import db
import uuid
from datetime import datetime

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = db.Column(db.String(36), db.ForeignKey('rooms.id'))
    sender_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    message = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='text')
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
