from extensions import db
import uuid
from datetime import datetime

class GuestFaceProfile(db.Model):
    """
    Stores host-uploaded biometric face encodings for a specific room.
    Each record represents one detected face from the host's bulk upload.
    """
    __tablename__ = 'guest_face_profiles'

    id          = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id     = db.Column(db.String(36), db.ForeignKey('rooms.id'), nullable=False, index=True)
    host_id     = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)

    # Label/name from filename (e.g. "john_doe.jpg" → "john_doe")
    label       = db.Column(db.String(255), nullable=True)

    # Pickled face_recognition encoding (128-dim float array)
    face_encoding = db.Column(db.LargeBinary, nullable=False)

    # Original image stored as JPEG bytes for audit/display thumbnail
    image_bytes = db.Column(db.LargeBinary, nullable=True)

    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

class BiometricVerificationLog(db.Model):
    """
    Audit log for every face-verification attempt against the guest database.
    """
    __tablename__ = 'biometric_verification_logs'

    id              = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id         = db.Column(db.String(36), db.ForeignKey('rooms.id'), nullable=False, index=True)
    user_id         = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)

    # 'matched' | 'no_match' | 'no_face' | 'multiple_faces' | 'error'
    result          = db.Column(db.String(30), nullable=False)
    matched_profile_id = db.Column(db.String(36), db.ForeignKey('guest_face_profiles.id'), nullable=True)
    confidence      = db.Column(db.Float, nullable=True)
    distance        = db.Column(db.Float, nullable=True)

    # Security flags: unknown, multiple_faces, no_face, suspicious
    alert_type      = db.Column(db.String(50), nullable=True)

    timestamp       = db.Column(db.DateTime, default=datetime.utcnow)
