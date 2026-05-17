from flask_socketio import emit, join_room, leave_room
from extensions import socketio

@socketio.on('join_room', namespace='/conference')
def on_join(data):
    room_code = data.get('room_code')
    user_id = data.get('user_id')
    name = data.get('name')
    peer_id = data.get('peer_id')
    
    join_room(room_code)
    join_room(f"user_{user_id}")
    
    # Broadcast to others in the room
    emit('user_joined', {
        'user_id': user_id,
        'name': name,
        'peer_id': peer_id
    }, room=room_code, include_self=False)

@socketio.on('host_dashboard_connect', namespace='/conference')
def on_host_dashboard_connect(data):
    user_id = data.get('user_id')
    if user_id:
        join_room(f"host_alerts_{user_id}")

@socketio.on('leave_room', namespace='/conference')
def on_leave(data):
    room_code = data.get('room_code')
    user_id = data.get('user_id')
    
    leave_room(room_code)
    
    emit('user_left', {
        'user_id': user_id
    }, room=room_code, include_self=False)

@socketio.on('offer', namespace='/conference')
def handle_offer(data):
    # Pass offer to specific user or broadcast
    emit('receive_offer', data, room=data.get('to'))

@socketio.on('answer', namespace='/conference')
def handle_answer(data):
    emit('receive_answer', data, room=data.get('to'))

@socketio.on('ice_candidate', namespace='/conference')
def handle_ice_candidate(data):
    emit('receive_ice', data, room=data.get('to'))

@socketio.on('chat_message', namespace='/conference')
def handle_chat_message(data):
    room_code = data.get('room_code')
    emit('chat_message', {
        'sender': data.get('sender'),
        'message': data.get('message'),
        'timestamp': data.get('timestamp'),
        'is_announcement': data.get('is_announcement', False)
    }, room=room_code)

@socketio.on('private_message', namespace='/conference')
def handle_private_message(data):
    target_id = data.get('target_user_id')
    emit('private_message', {
        'sender': data.get('sender'),
        'message': data.get('message'),
        'timestamp': data.get('timestamp')
    }, room=f"user_{target_id}")

@socketio.on('chat_locked', namespace='/conference')
def handle_chat_locked(data):
    room_code = data.get('room_code')
    is_locked = data.get('is_locked')
    emit('chat_locked', {'is_locked': is_locked}, room=room_code)

@socketio.on('launch_live_quiz', namespace='/conference')
def handle_launch_live_quiz(data):
    room_code = data.get('room_code')
    emit('launch_live_quiz', data, room=room_code)

@socketio.on('submit_quiz_answer', namespace='/conference')
def handle_submit_quiz_answer(data):
    room_code = data.get('room_code')
    host_id = data.get('host_id')
    if host_id:
        emit('quiz_answer_submitted', data, room=f"user_{host_id}")

@socketio.on('join_waiting_room', namespace='/conference')
def on_join_waiting(data):
    room_code = data.get('room_code')
    user_id = data.get('user_id')
    name = data.get('name')
    
    # Send only to host. We can broadcast to room_code, and frontend host filters it
    # Or join a specific room like 'host_room_code'
    join_room(f"waiting_{user_id}") # user listens here for approval
    
    emit('participant_waiting', {
        'user_id': user_id,
        'name': name
    }, room=room_code) # Host should be in room_code

@socketio.on('approve_participant', namespace='/conference')
def on_approve(data):
    user_id = data.get('user_id')
    room_code = data.get('room_code')
    emit('participant_approved', {'room_code': room_code}, room=f"waiting_{user_id}")

@socketio.on('reject_participant', namespace='/conference')
def on_reject(data):
    user_id = data.get('user_id')
    emit('participant_rejected', {}, room=f"waiting_{user_id}")

@socketio.on('room_state_changed', namespace='/conference')
def on_state_change(data):
    room_code = data.get('room_code')
    emit('room_state_updated', data, room=room_code)

@socketio.on('force_mute', namespace='/conference')
def on_force_mute(data):
    target_user_id = data.get('target_user_id')
    emit('force_mute', {}, room=f"user_{target_user_id}")

@socketio.on('force_video_off', namespace='/conference')
def on_force_video_off(data):
    target_user_id = data.get('target_user_id')
    emit('force_video_off', {}, room=f"user_{target_user_id}")

@socketio.on('force_leave', namespace='/conference')
def on_force_leave(data):
    target_user_id = data.get('target_user_id')
    emit('force_leave', {}, room=f"user_{target_user_id}")

@socketio.on('raise_hand', namespace='/conference')
def on_raise_hand(data):
    room_code = data.get('room_code')
    user_name = data.get('user_name', 'A participant')
    emit('hand_raised', {'user_name': user_name}, room=room_code, include_self=False)

@socketio.on('toggle_whiteboard', namespace='/conference')
def on_toggle_whiteboard(data):
    room_code = data.get('room_code')
    is_active = data.get('is_active')
    emit('whiteboard_toggled', {'is_active': is_active}, room=room_code)

@socketio.on('draw_line', namespace='/conference')
def on_draw_line(data):
    room_code = data.get('room_code')
    emit('draw_line', data, room=room_code, include_self=False)

@socketio.on('clear_whiteboard', namespace='/conference')
def on_clear_whiteboard(data):
    room_code = data.get('room_code')
    emit('clear_whiteboard', {}, room=room_code)

@socketio.on('promote_cohost', namespace='/conference')
def on_promote_cohost(data):
    target_user_id = data.get('target_user_id')
    room_code = data.get('room_code')
    name = data.get('name', 'Participant')
    # Notify the promoted participant
    emit('promoted_to_cohost', {'room_code': room_code}, room=f"user_{target_user_id}")
    # Notify the whole room
    emit('cohost_promoted', {'name': name}, room=room_code)

@socketio.on('name_changed', namespace='/conference')
def on_name_changed(data):
    room_code = data.get('room_code')
    old_name = data.get('old_name')
    new_name = data.get('new_name')
    email = data.get('email', 'unknown')
    host_id = data.get('host_id')
    from datetime import datetime
    from extensions import db
    try:
        from models import SecurityLog
        log = SecurityLog(
            user_id=data.get('user_id'),
            room_id=room_code,
            event_type='name_change',
            details=f"Name changed from '{old_name}' to '{new_name}' (email: {email})"
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass
    if host_id:
        emit('name_change_alert', {
            'old_name': old_name,
            'new_name': new_name,
            'email': email,
            'time': datetime.utcnow().isoformat()
        }, room=f"user_{host_id}")
    # Also broadcast to any coordinator monitoring this room
    from extensions import socketio as sio
    sio.emit('name_change_alert', {
        'old_name': old_name,
        'new_name': new_name,
        'email': email,
        'room_code': room_code,
        'time': datetime.utcnow().isoformat()
    }, namespace='/coordinator', broadcast=True)

@socketio.on('pause_exam', namespace='/conference')
def on_pause_exam(data):
    room_code = data.get('room_code')
    emit('exam_paused', {'message': 'Exam has been paused by the host. Please wait.'}, room=room_code)

@socketio.on('resume_exam', namespace='/conference')
def on_resume_exam(data):
    room_code = data.get('room_code')
    emit('exam_resumed', {'message': 'Exam has been resumed. You may continue.'}, room=room_code)

@socketio.on('guest_dashboard_connect', namespace='/conference')
def on_guest_dashboard_connect(data):
    """Guest connects from dashboard to receive session notifications."""
    user_id = data.get('user_id')
    if user_id:
        join_room(f"user_{user_id}")

@socketio.on('room_started', namespace='/conference')
def on_room_started(data):
    """Host broadcasts that a room has gone live. Notify all waiting/attending users."""
    room_code = data.get('room_code')
    title = data.get('title', 'A session')
    room_type = data.get('room_type', 'meeting')
    emit('session_started', {
        'room_code': room_code,
        'title': title,
        'room_type': room_type,
        'message': f"{'📝 Exam' if room_type == 'exam' else '📡 Class'} '{title}' has started!"
    }, room=room_code)


# ─── Feature 8 / 11: Screen Share Notifications ──────────────────────────────
@socketio.on('screen_share_started', namespace='/conference')
def on_screen_share_started(data):
    """Broadcast to room that a participant has started screen sharing."""
    room_code = data.get('room_code')
    user_name = data.get('user_name', 'A participant')
    emit('screen_share_started', {'user_name': user_name}, room=room_code, include_self=False)

@socketio.on('screen_share_stopped', namespace='/conference')
def on_screen_share_stopped(data):
    """Broadcast to room that screen sharing has ended."""
    room_code = data.get('room_code')
    user_name = data.get('user_name', 'A participant')
    emit('screen_share_stopped', {'user_name': user_name}, room=room_code, include_self=False)


# ─── Feature 8: Mic / Camera status broadcasts ───────────────────────────────
@socketio.on('mute_status', namespace='/conference')
def on_mute_status(data):
    """Broadcast mute state so others can update the participant list."""
    room_code = data.get('room_code')
    muted = data.get('muted', False)
    emit('participant_mute_status', {
        'muted': muted
    }, room=room_code, include_self=False)

@socketio.on('video_status', namespace='/conference')
def on_video_status(data):
    """Broadcast camera state so others can update the participant list."""
    room_code = data.get('room_code')
    video_off = data.get('video_off', False)
    emit('participant_video_status', {
        'video_off': video_off
    }, room=room_code, include_self=False)


# ─── Feature 14 / 23: Push violation warning to guest's notification room ─────
@socketio.on('violation_warning_notify', namespace='/conference')
def on_violation_warning_notify(data):
    """Coordinator or proctoring system pushes a warning to a guest's notification room."""
    target_user_id = data.get('user_id')
    message = data.get('message', 'A violation was detected during your exam.')
    if target_user_id:
        emit('guest_violation_warning', {
            'message': message
        }, room=f"user_{target_user_id}")

