from extensions import db
import uuid
from datetime import datetime

class CoordinatorLog(db.Model):
    __tablename__ = 'coordinator_logs'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    coordinator_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    exam_id = db.Column(db.String(36), db.ForeignKey('exams.id'))
    action_type = db.Column(db.String(50), nullable=False)
    target_user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    notes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class CoordinatorPresence(db.Model):
    __tablename__ = 'coordinator_presence'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    coordinator_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    exam_id = db.Column(db.String(36), db.ForeignKey('exams.id'))
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    confidence_score = db.Column(db.Float)
