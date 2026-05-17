from extensions import db
import uuid
from datetime import datetime

class CloudFile(db.Model):
    __tablename__ = 'cloud_files'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    host_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer) # in bytes
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
