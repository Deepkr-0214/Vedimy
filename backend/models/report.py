from extensions import db
import uuid
from datetime import datetime

class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id = db.Column(db.String(36), db.ForeignKey('exams.id'))
    generated_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    report_type = db.Column(db.String(30), default='exam_summary')
    pdf_path = db.Column(db.String(500))
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
