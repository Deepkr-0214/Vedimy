from flask_socketio import emit, join_room
from flask import request
from extensions import socketio

@socketio.on('connect', namespace='/coordinator')
def on_connect():
    pass

@socketio.on('join_monitor', namespace='/coordinator')
def on_join_monitor(data):
    exam_id = data.get('exam_id')
    if exam_id:
        join_room(f'coordinator_{exam_id}')

@socketio.on('send_warning', namespace='/coordinator')
def handle_send_warning(data):
    user_id = data.get('user_id')
    message = data.get('message', 'Warning from coordinator')
    # Send to exam-room.js (which joined /conference for exam_warning)
    socketio.emit('exam_warning', {
        'message': message, 'warnings_remaining': 2
    }, namespace='/conference', room=f"user_{user_id}")

@socketio.on('remove_user', namespace='/coordinator')
def handle_remove_user(data):
    user_id = data.get('user_id')
    socketio.emit('exam_terminated', {
        'reason': 'Removed by coordinator'
    }, namespace='/conference', room=f"user_{user_id}")

@socketio.on('terminate_exam', namespace='/coordinator')
def handle_terminate_exam(data):
    """Force auto-submit for all candidates in the exam room."""
    exam_id = data.get('exam_id')
    reason = data.get('reason', 'Exam terminated by coordinator')
    if exam_id:
        # Broadcast to all users in the exam room on the conference namespace
        socketio.emit('exam_terminated', {
            'reason': reason
        }, namespace='/conference', room=exam_id)
        # Also emit to the proctoring namespace as a fallback
        socketio.emit('exam_terminated', {
            'reason': reason
        }, namespace='/proctoring', room=exam_id)
