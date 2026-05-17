"""
Models for Feature 31: Smart Guest Registration Form System.

GuestRegistrationForm    — holds the secure token the host shares.
GuestRegistrationSubmission — each guest's pre-registration details +
                              link to the GuestFaceProfile created from
                              their uploaded biometric image.
"""

from extensions import db
import uuid
from datetime import datetime


class GuestRegistrationForm(db.Model):
    """
    One form per room (host can regenerate the token at will).
    The shareable URL is: /pages/guest-register.html?token=<token>
    """
    __tablename__ = 'guest_registration_forms'

    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id    = db.Column(db.String(36), db.ForeignKey('rooms.id'), nullable=False, index=True)
    host_id    = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)

    # Secure random token embedded in the public link
    token      = db.Column(db.String(64), unique=True, nullable=False, index=True,
                           default=lambda: str(uuid.uuid4()).replace('-', '') + str(uuid.uuid4()).replace('-', ''))

    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    submissions = db.relationship('GuestRegistrationSubmission', backref='form', lazy='dynamic',
                                  cascade='all, delete-orphan')


class GuestRegistrationSubmission(db.Model):
    """
    One record per guest who completed the pre-registration form.
    After biometric processing, face_profile_id points to the
    GuestFaceProfile that will be matched during room entry.
    """
    __tablename__ = 'guest_registration_submissions'

    id             = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    form_id        = db.Column(db.String(36), db.ForeignKey('guest_registration_forms.id'), nullable=False, index=True)
    room_id        = db.Column(db.String(36), db.ForeignKey('rooms.id'), nullable=False, index=True)

    guest_name     = db.Column(db.String(255), nullable=False)
    contact_number = db.Column(db.String(50), nullable=True)
    address        = db.Column(db.Text, nullable=True)

    # Set after successful face encoding
    face_profile_id = db.Column(db.String(36), db.ForeignKey('guest_face_profiles.id'), nullable=True)

    # 'pending' | 'encoded' | 'failed'
    face_status    = db.Column(db.String(30), default='pending')
    face_error_msg = db.Column(db.String(255), nullable=True)

    submitted_at   = db.Column(db.DateTime, default=datetime.utcnow)
