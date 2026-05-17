"""
Feature 31: Smart Guest Registration Form System — Backend Routes

POST   /api/guest-reg/<room_id>/generate-link     — host: create/refresh form token
GET    /api/guest-reg/<token>/form-info            — public: room info for form page
POST   /api/guest-reg/<token>/submit               — public: submit guest details + face
GET    /api/guest-reg/<room_id>/submissions        — host: list all submissions
DELETE /api/guest-reg/<room_id>/submissions/<sid>  — host: delete a submission
GET    /api/guest-reg/<room_id>/submission/<sid>/thumbnail — host: face thumbnail
"""

from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from models import Room, User
from models.guest_face import GuestFaceProfile
from models.guest_registration import GuestRegistrationForm, GuestRegistrationSubmission
from extensions import db
from services import face_service
import uuid, pickle
from datetime import datetime

guest_reg_bp = Blueprint('guest_reg', __name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _require_host(room_id, user_id):
    return Room.query.filter_by(id=room_id, host_id=user_id).first()


# ─── Generate / Refresh Form Link ────────────────────────────────────────────

@guest_reg_bp.route('/<room_id>/generate-link', methods=['POST'])
@jwt_required()
def generate_link(room_id):
    """
    Host calls this to get a shareable registration form token for their room.
    If a form already exists it is returned; regenerate=true creates a fresh token.
    """
    user_id = get_jwt_identity()
    room = _require_host(room_id, user_id)
    if not room:
        return jsonify({"error": "Room not found or access denied"}), 403

    data = request.get_json(silent=True) or {}
    regenerate = data.get('regenerate', False)

    form = GuestRegistrationForm.query.filter_by(room_id=room_id, is_active=True).first()

    if form and regenerate:
        # Deactivate old form and create fresh one
        form.is_active = False
        db.session.flush()
        form = None

    if not form:
        form = GuestRegistrationForm(
            id=str(uuid.uuid4()),
            room_id=room_id,
            host_id=user_id,
            token=str(uuid.uuid4()).replace('-', '') + str(uuid.uuid4()).replace('-', ''),
            is_active=True
        )
        db.session.add(form)
        db.session.commit()

    return jsonify({
        "form_id": form.id,
        "token": form.token,
        "room_id": room_id,
        "room_title": room.title,
        "created_at": form.created_at.isoformat()
    }), 200


# ─── Public: Form Info (no auth) ─────────────────────────────────────────────

@guest_reg_bp.route('/<token>/form-info', methods=['GET'])
def form_info(token):
    """Public endpoint — returns room details so the form page can display context."""
    form = GuestRegistrationForm.query.filter_by(token=token, is_active=True).first()
    if not form:
        return jsonify({"error": "Invalid or expired registration link"}), 404

    room = Room.query.get(form.room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404

    host = User.query.get(form.host_id)

    return jsonify({
        "room_title": room.title,
        "room_type": room.room_type,
        "host_name": host.name if host else "Unknown Host",
        "form_id": form.id,
        "room_id": room.id
    }), 200


# ─── Public: Submit Registration ──────────────────────────────────────────────

@guest_reg_bp.route('/<token>/submit', methods=['POST'])
def submit_registration(token):
    """
    Public endpoint — guest submits their details + biometric image.
    The image is processed immediately: face detected, encoded, stored
    as a GuestFaceProfile so they can be verified on room join.
    """
    form = GuestRegistrationForm.query.filter_by(token=token, is_active=True).first()
    if not form:
        return jsonify({"error": "Invalid or expired registration link"}), 404

    room = Room.query.get(form.room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404

    # ── Parse form fields ──
    guest_name = request.form.get('guest_name', '').strip()
    contact    = request.form.get('contact_number', '').strip()
    address    = request.form.get('address', '').strip()
    image_file = request.files.get('face_image')

    if not guest_name:
        return jsonify({"error": "Name is required"}), 400
    if not image_file:
        return jsonify({"error": "Biometric face image is required"}), 400
    if not _allowed(image_file.filename):
        return jsonify({"error": "Unsupported image format. Use JPG, PNG, or WEBP."}), 400

    image_bytes = image_file.read()

    # ── AI face encoding ──
    encodings_list, thumb_bytes, err = face_service.encode_face_from_bytes(image_bytes)

    submission = GuestRegistrationSubmission(
        id=str(uuid.uuid4()),
        form_id=form.id,
        room_id=form.room_id,
        guest_name=guest_name,
        contact_number=contact,
        address=address,
        face_status='pending'
    )

    if err or not encodings_list:
        # Store submission but mark face as failed
        submission.face_status = 'failed'
        submission.face_error_msg = err or 'No face detected in the uploaded image'
        db.session.add(submission)
        db.session.commit()
        return jsonify({
            "error": submission.face_error_msg,
            "submitted": True,
            "face_status": "failed"
        }), 422

    # Use first encoding (we expect one face per registration photo)
    encoding = encodings_list[0]

    profile = GuestFaceProfile(
        id=str(uuid.uuid4()),
        room_id=form.room_id,
        host_id=form.host_id,
        label=guest_name,
        face_encoding=pickle.dumps(encoding),
        image_bytes=thumb_bytes
    )
    db.session.add(profile)
    db.session.flush()

    submission.face_profile_id = profile.id
    submission.face_status = 'encoded'
    db.session.add(submission)
    db.session.commit()

    return jsonify({
        "message": "Registration successful! Your biometric data has been saved.",
        "submitted": True,
        "face_status": "encoded",
        "submission_id": submission.id
    }), 201


# ─── Host: List All Submissions ───────────────────────────────────────────────

@guest_reg_bp.route('/<room_id>/submissions', methods=['GET'])
@jwt_required()
def list_submissions(room_id):
    user_id = get_jwt_identity()
    room = _require_host(room_id, user_id)
    if not room:
        return jsonify({"error": "Access denied"}), 403

    # Find all active forms for this room
    forms = GuestRegistrationForm.query.filter_by(room_id=room_id).all()
    form_ids = [f.id for f in forms]

    if not form_ids:
        return jsonify([]), 200

    subs = (GuestRegistrationSubmission.query
            .filter(GuestRegistrationSubmission.form_id.in_(form_ids))
            .order_by(GuestRegistrationSubmission.submitted_at.desc())
            .all())

    return jsonify([{
        "id":             s.id,
        "guest_name":     s.guest_name,
        "contact_number": s.contact_number,
        "address":        s.address,
        "face_status":    s.face_status,
        "face_error_msg": s.face_error_msg,
        "face_profile_id":s.face_profile_id,
        "has_thumbnail":  s.face_profile_id is not None,
        "submitted_at":   s.submitted_at.isoformat()
    } for s in subs]), 200


# ─── Host: Delete Submission ──────────────────────────────────────────────────

@guest_reg_bp.route('/<room_id>/submissions/<sub_id>', methods=['DELETE'])
@jwt_required()
def delete_submission(room_id, sub_id):
    user_id = get_jwt_identity()
    room = _require_host(room_id, user_id)
    if not room:
        return jsonify({"error": "Access denied"}), 403

    sub = GuestRegistrationSubmission.query.filter_by(id=sub_id, room_id=room_id).first_or_404()

    # Also remove the linked biometric profile so it won't match during verification
    if sub.face_profile_id:
        profile = GuestFaceProfile.query.get(sub.face_profile_id)
        if profile:
            db.session.delete(profile)

    db.session.delete(sub)
    db.session.commit()
    return jsonify({"message": "Submission deleted"}), 200


# ─── Host: Face Thumbnail for a Submission ───────────────────────────────────

@guest_reg_bp.route('/<room_id>/submission/<sub_id>/thumbnail', methods=['GET'])
@jwt_required()
def submission_thumbnail(room_id, sub_id):
    user_id = get_jwt_identity()
    room = _require_host(room_id, user_id)
    if not room:
        return jsonify({"error": "Access denied"}), 403

    sub = GuestRegistrationSubmission.query.filter_by(id=sub_id, room_id=room_id).first_or_404()
    if not sub.face_profile_id:
        return jsonify({"error": "No face data"}), 404

    profile = GuestFaceProfile.query.get(sub.face_profile_id)
    if not profile or not profile.image_bytes:
        return jsonify({"error": "No thumbnail"}), 404

    return Response(profile.image_bytes, mimetype='image/jpeg')


# ─── Host: Get Active Form Token ─────────────────────────────────────────────

@guest_reg_bp.route('/<room_id>/active-form', methods=['GET'])
@jwt_required()
def get_active_form(room_id):
    """Returns current active form token for the room if it exists."""
    user_id = get_jwt_identity()
    room = _require_host(room_id, user_id)
    if not room:
        return jsonify({"error": "Access denied"}), 403

    form = GuestRegistrationForm.query.filter_by(room_id=room_id, is_active=True).first()
    if not form:
        return jsonify({"exists": False}), 200

    return jsonify({
        "exists": True,
        "form_id": form.id,
        "token": form.token,
        "created_at": form.created_at.isoformat()
    }), 200
