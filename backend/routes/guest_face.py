"""
Routes for host-side guest biometric management.

POST /api/guest-face/<room_id>/upload       — bulk upload images (multipart)
GET  /api/guest-face/<room_id>/profiles     — list stored profiles
DELETE /api/guest-face/<room_id>/profiles/<profile_id>  — remove one profile
DELETE /api/guest-face/<room_id>/profiles   — clear all profiles for a room
POST /api/guest-face/<room_id>/verify       — verify live face against pool (JWT)
GET  /api/guest-face/<room_id>/logs         — verification audit logs
PATCH /api/guest-face/<room_id>/mode        — set biometric_mode for the room
GET  /api/guest-face/<room_id>/thumbnail/<profile_id>  — serve thumbnail image
"""

from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import Room, User
from models.guest_face import GuestFaceProfile, BiometricVerificationLog
from extensions import db
from services import face_service
import pickle, uuid, json
from datetime import datetime

guest_face_bp = Blueprint('guest_face', __name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _require_host(room_id, user_id):
    """Return room if caller is the host, else None."""
    return Room.query.filter_by(id=room_id, host_id=user_id).first()


# ─── Bulk Upload ─────────────────────────────────────────────────────────────
@guest_face_bp.route('/<room_id>/upload', methods=['POST'])
@jwt_required()
def bulk_upload(room_id):
    """
    Accept multiple image files via multipart/form-data (field name: 'images').
    Processes each image: detects faces, stores encoding + thumbnail.
    Returns per-file results.
    """
    user_id = get_jwt_identity()
    room = _require_host(room_id, user_id)
    if not room:
        return jsonify({"error": "Room not found or access denied"}), 403

    files = request.files.getlist('images')
    if not files:
        return jsonify({"error": "No images provided"}), 400

    results = []
    added = 0

    for f in files:
        if not f or not f.filename:
            continue
        if not _allowed(f.filename):
            results.append({"filename": f.filename, "status": "skipped", "reason": "Unsupported format"})
            continue

        image_bytes = f.read()
        label = f.filename.rsplit('.', 1)[0]  # strip extension

        encodings_list, thumb_bytes, err = face_service.encode_face_from_bytes(image_bytes)

        if err or not encodings_list:
            results.append({"filename": f.filename, "status": "failed", "reason": err or "No face found"})
            continue

        # Store one profile record per detected face
        for idx, encoding in enumerate(encodings_list):
            face_label = label if len(encodings_list) == 1 else f"{label}_{idx+1}"
            profile = GuestFaceProfile(
                id=str(uuid.uuid4()),
                room_id=room_id,
                host_id=user_id,
                label=face_label,
                face_encoding=pickle.dumps(encoding),
                image_bytes=thumb_bytes
            )
            db.session.add(profile)
            added += 1

        results.append({
            "filename": f.filename,
            "status": "success",
            "faces_detected": len(encodings_list),
            "label": label
        })

    db.session.commit()
    return jsonify({"added": added, "results": results}), 200


# ─── List Profiles ────────────────────────────────────────────────────────────
@guest_face_bp.route('/<room_id>/profiles', methods=['GET'])
@jwt_required()
def list_profiles(room_id):
    user_id = get_jwt_identity()
    room = _require_host(room_id, user_id)
    if not room:
        return jsonify({"error": "Access denied"}), 403

    profiles = GuestFaceProfile.query.filter_by(room_id=room_id).order_by(GuestFaceProfile.created_at).all()
    return jsonify([{
        "id": p.id,
        "label": p.label,
        "has_thumbnail": p.image_bytes is not None,
        "created_at": p.created_at.isoformat()
    } for p in profiles]), 200


# ─── Thumbnail ────────────────────────────────────────────────────────────────
@guest_face_bp.route('/<room_id>/thumbnail/<profile_id>', methods=['GET'])
@jwt_required()
def get_thumbnail(room_id, profile_id):
    user_id = get_jwt_identity()
    room = _require_host(room_id, user_id)
    if not room:
        return jsonify({"error": "Access denied"}), 403

    profile = GuestFaceProfile.query.filter_by(id=profile_id, room_id=room_id).first_or_404()
    if not profile.image_bytes:
        return jsonify({"error": "No thumbnail"}), 404

    return Response(profile.image_bytes, mimetype='image/jpeg')


# ─── Delete One Profile ───────────────────────────────────────────────────────
@guest_face_bp.route('/<room_id>/profiles/<profile_id>', methods=['DELETE'])
@jwt_required()
def delete_profile(room_id, profile_id):
    user_id = get_jwt_identity()
    room = _require_host(room_id, user_id)
    if not room:
        return jsonify({"error": "Access denied"}), 403

    profile = GuestFaceProfile.query.filter_by(id=profile_id, room_id=room_id).first_or_404()
    db.session.delete(profile)
    db.session.commit()
    return jsonify({"message": "Profile deleted"}), 200


# ─── Clear All Profiles ───────────────────────────────────────────────────────
@guest_face_bp.route('/<room_id>/profiles', methods=['DELETE'])
@jwt_required()
def clear_profiles(room_id):
    user_id = get_jwt_identity()
    room = _require_host(room_id, user_id)
    if not room:
        return jsonify({"error": "Access denied"}), 403

    deleted = GuestFaceProfile.query.filter_by(room_id=room_id).delete()
    db.session.commit()
    return jsonify({"message": f"Cleared {deleted} profiles"}), 200


# ─── Verify Live Face Against Guest Pool ────────────────────────────────────
@guest_face_bp.route('/<room_id>/verify', methods=['POST'])
@jwt_required()
def verify_against_pool(room_id):
    """
    Guest calls this endpoint with their live camera frame.
    System matches against all stored profiles for the room.
    Also logs the attempt and triggers security alert if needed.
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    image_b64 = data.get('image')

    if not image_b64:
        return jsonify({"error": "No image provided"}), 400

    room = Room.query.get_or_404(room_id)

    # Load biometric mode from security_flags
    try:
        flags = json.loads(room.security_flags_json or '{}')
    except Exception:
        flags = {}

    biometric_mode = flags.get('biometric_mode', 'required')

    if biometric_mode == 'disabled':
        return jsonify({"verified": True, "mode": "disabled", "label": "", "confidence": 1.0}), 200

    # Load all profiles for this room
    profiles = GuestFaceProfile.query.filter_by(room_id=room_id).all()

    if not profiles:
        # No guest profiles uploaded → fall back to self-registered face
        user = User.query.get(user_id)
        if user and user.face_registered and user.face_encoding:
            stored = pickle.loads(user.face_encoding)
            result = face_service.verify_face(image_b64, stored)
            _log_attempt(room_id, user_id, result, None)
            return jsonify({
                "verified": result.get("match", False),
                "mode": "self_registered",
                "confidence": result.get("confidence", 0),
                "error": result.get("error")
            }), 200
        return jsonify({"error": "No biometric profiles found for this room"}), 400

    # Build pool for matching
    pool = []
    for p in profiles:
        try:
            enc = pickle.loads(p.face_encoding)
            pool.append({"id": p.id, "label": p.label or "", "encoding": enc})
        except Exception:
            continue

    result = face_service.verify_against_pool(image_b64, pool)

    # Determine alert type
    alert_type = None
    err = result.get("error")
    if err == "no_face":
        alert_type = "no_face"
    elif err == "multiple_faces":
        alert_type = "multiple_faces"
    elif err == "no_match":
        alert_type = "unknown_face"

    matched_id = result.get("profile_id") if result.get("verified") else None
    _log_attempt(room_id, user_id, result, matched_id, alert_type)

    return jsonify({
        "verified": result.get("verified", False),
        "mode": "guest_pool",
        "label": result.get("label", ""),
        "confidence": result.get("confidence", 0),
        "error": err,
        "alert": alert_type
    }), 200


def _log_attempt(room_id, user_id, result, matched_profile_id, alert_type=None):
    try:
        log = BiometricVerificationLog(
            id=str(uuid.uuid4()),
            room_id=room_id,
            user_id=user_id,
            result='matched' if result.get('verified') or result.get('match') else (result.get('error') or 'no_match'),
            matched_profile_id=matched_profile_id,
            confidence=result.get('confidence'),
            distance=result.get('distance'),
            alert_type=alert_type
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass  # Log failure should never crash verification


# ─── Verification Logs ───────────────────────────────────────────────────────
@guest_face_bp.route('/<room_id>/logs', methods=['GET'])
@jwt_required()
def get_verification_logs(room_id):
    user_id = get_jwt_identity()
    room = _require_host(room_id, user_id)
    if not room:
        return jsonify({"error": "Access denied"}), 403

    logs = (BiometricVerificationLog.query
            .filter_by(room_id=room_id)
            .order_by(BiometricVerificationLog.timestamp.desc())
            .limit(200).all())

    return jsonify([{
        "id": l.id,
        "user_id": l.user_id,
        "result": l.result,
        "matched_profile_id": l.matched_profile_id,
        "confidence": l.confidence,
        "alert_type": l.alert_type,
        "timestamp": l.timestamp.isoformat()
    } for l in logs]), 200


# ─── Set Biometric Mode ──────────────────────────────────────────────────────
@guest_face_bp.route('/<room_id>/mode', methods=['PATCH'])
@jwt_required()
def set_biometric_mode(room_id):
    """
    biometric_mode options:
      'required'       — all must pass biometric check
      'exam_only'      — only for exam rooms
      'disabled'       — skip biometric entirely
    """
    user_id = get_jwt_identity()
    room = _require_host(room_id, user_id)
    if not room:
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json()
    mode = data.get('biometric_mode')
    if mode not in ('required', 'exam_only', 'disabled'):
        return jsonify({"error": "Invalid mode"}), 400

    try:
        flags = json.loads(room.security_flags_json or '{}')
    except Exception:
        flags = {}

    flags['biometric_mode'] = mode
    room.security_flags_json = json.dumps(flags)
    db.session.commit()
    return jsonify({"message": "Biometric mode updated", "biometric_mode": mode}), 200
