from extensions import db
from datetime import datetime, timezone

class ChatHistory(db.Model):
    __tablename__ = 'chat_history'

    id = db.Column(db.Integer, primary_key=True)
    user_type = db.Column(db.String(50), nullable=False, default='guest')
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'user_type': self.user_type,
            'message': self.message,
            'response': self.response,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

class SupportLog(db.Model):
    __tablename__ = 'support_logs'

    id = db.Column(db.Integer, primary_key=True)
    issue = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='open')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'issue': self.issue,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
