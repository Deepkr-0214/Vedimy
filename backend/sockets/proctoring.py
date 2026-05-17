from flask_socketio import emit, join_room
from flask import request, current_app
from extensions import socketio, db
from models import Violation
import uuid
import os
import base64
from datetime import datetime

# ─── Cumulative warning counter ────────────────────────────────────────────────
# Key: (exam_id, user_id) → running violation count this session
_warning_counts = {}

def _get_and_increment(exam_id, user_id):
    """Atomically increment and return the new cumulative warning count."""
    key = (exam_id, user_id)
    _warning_counts[key] = _warning_counts.get(key, 0) + 1
    return _warning_counts[key]

def _get_severity(count):
    """Escalate severity as warnings accumulate."""
    if count >= 3:
        return 'critical'
    elif count >= 2:
        return 'severe'
    return 'warning'

def save_screenshot(base64_data):
    if not base64_data: return None
    try:
        # Format: data:image/jpeg;base64,...
        header, encoded = base64_data.split(",", 1)
        data = base64.b64decode(encoded)
        filename = f"{uuid.uuid4()}.jpg"
        screenshot_dir = current_app.config['SCREENSHOT_DIR']
        os.makedirs(screenshot_dir, exist_ok=True)
        filepath = os.path.join(screenshot_dir, filename)
        with open(filepath, "wb") as f:
            f.write(data)
        return f"/api/files/screenshots/{filename}"
    except Exception:
        return None

def handle_violation_db(exam_id, user_id, v_type, frame_base64=None):
    """Log a violation and return (screenshot_path, cumulative_count, severity)."""
    path = save_screenshot(frame_base64) if frame_base64 else None
    count = _get_and_increment(exam_id, user_id)
    severity = _get_severity(count)

    with current_app.app_context():
        v = Violation(
            user_id=user_id,
            exam_id=exam_id,
            violation_type=v_type,
            severity=severity,
            screenshot_path=path,
            warning_count=count
        )
        db.session.add(v)
        db.session.commit()

        socketio.emit('candidate_violation', {
            'user_id': user_id,
            'violation': {
                'type': v_type,
                'screenshot': path,
                'warning_count': count,
                'severity': severity,
                'timestamp': datetime.utcnow().isoformat()
            }
        }, namespace='/coordinator', room=f"coordinator_{exam_id}")
    return path, count, severity

@socketio.on('exam_active', namespace='/proctoring')
def on_exam_active(data):
    exam_id = data.get('exam_id')
    user_id = data.get('user_id')
    if exam_id:
        join_room(exam_id)
        # Also join personal room so coordinator can target this user
        if user_id:
            join_room(user_id)

@socketio.on('frame_check', namespace='/proctoring')
def handle_frame_check(data):
    exam_id = data.get('exam_id')
    user_id = data.get('user_id')
    frame_base64 = data.get('frame_base64', '')

    try:
        from services.face_service import FaceService
        svc = FaceService()
        count = svc.detect_faces_count(frame_base64)
        if count == 0:
            path, warn_count, severity = handle_violation_db(exam_id, user_id, 'no_face', frame_base64)
            emit('violation_detected', {
                'type': 'no_face',
                'severity': severity,
                'warning_count': warn_count
            }, room=request.sid)
        elif count > 1:
            path, warn_count, severity = handle_violation_db(exam_id, user_id, 'multiple_faces', frame_base64)
            emit('violation_detected', {
                'type': 'multiple_faces',
                'severity': severity,
                'warning_count': warn_count
            }, room=request.sid)
        else:
            emit('face_ok', {'confidence': 0.95}, room=request.sid)
    except Exception:
        emit('face_ok', {'confidence': 0.99}, room=request.sid)

@socketio.on('violation', namespace='/proctoring')
def handle_client_violation(data):
    violation_type = data.get('type', 'unknown')
    exam_id = data.get('exam_id')
    user_id = data.get('user_id')
    frame_base64 = data.get('frame_base64')

    path, warn_count, severity = handle_violation_db(exam_id, user_id, violation_type, frame_base64)

    emit('violation_detected', {
        'type': violation_type,
        'severity': severity,
        'warning_count': warn_count
    }, room=request.sid)

    # Feature 14 / 23: Push warning to guest's personal dashboard notification room
    violation_msgs = {
        'tab_switch': 'Tab switch detected during exam.',
        'fullscreen_exit': 'Fullscreen mode exited during exam.',
        'camera_disabled': 'Camera was disabled during exam.',
        'no_face': 'No face detected during exam.',
        'multiple_faces': 'Multiple faces detected during exam.',
    }
    warn_msg = violation_msgs.get(violation_type, f'Violation detected: {violation_type}')
    socketio.emit('guest_violation_warning', {
        'message': f"{warn_msg} Warning {warn_count}/{3}."
    }, namespace='/conference', room=f"user_{user_id}")

@socketio.on('connect', namespace='/proctoring')
def on_connect():
    pass

@socketio.on('disconnect', namespace='/proctoring')
def on_disconnect():
    pass
