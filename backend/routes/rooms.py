from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import Room, RoomParticipant, User, Exam, Attendance, LectureRecord, AILecture, CloudFile, Notification
from extensions import db
import string, random, uuid
from datetime import datetime
import json

rooms_bp = Blueprint('rooms', __name__)

def generate_room_code():
    chars = string.ascii_uppercase + string.digits
    return 'VDM-' + ''.join(random.choices(chars, k=4))

@rooms_bp.route('/create', methods=['POST'])
@jwt_required()
def create_room():
    data = request.get_json()
    user_id = get_jwt_identity()
    room_code = generate_room_code()
    # ensure unique
    while Room.query.filter_by(room_code=room_code).first():
        room_code = generate_room_code()

    room = Room(
        id=str(uuid.uuid4()),
        room_code=room_code,
        title=data.get('title', 'Untitled Room'),
        host_id=user_id,
        room_type=data.get('room_type', 'meeting'),
        max_participants=data.get('max_participants', 50),
        waiting_room_enabled=data.get('waiting_room_enabled', False),
        status='scheduled',
        security_flags_json=json.dumps(data.get('security_flags', {}))
    )
    db.session.add(room)
    db.session.flush()  # Flush to get room.id without full commit
    
    if room.room_type == 'exam':
        exam = Exam(
            id=str(uuid.uuid4()),
            room_id=room.id,
            title=room.title,
            host_id=user_id,
            duration_minutes=int(data.get('duration_minutes', 60)),
            instructions=data.get('instructions', '')
        )
        db.session.add(exam)
        
    db.session.commit()
    return jsonify({"room_code": room.room_code, "id": room.id, "title": room.title}), 201

@rooms_bp.route('/<room_code>/info', methods=['GET'])
def get_room_info_public(room_code):
    """Public endpoint — no auth needed. Returns basic room details for join page preview."""
    room = Room.query.filter_by(room_code=room_code).first_or_404()
    host = User.query.get(room.host_id)
    return jsonify({
        "id": room.id,
        "room_code": room.room_code,
        "title": room.title,
        "room_type": room.room_type,
        "is_active": room.is_active,
        "status": room.status,
        "is_locked": room.is_locked,
        "host_name": host.name if host else "Unknown Host",
        "security_flags_json": room.security_flags_json or '{}'
    }), 200

@rooms_bp.route('/<room_code>', methods=['GET'])
@jwt_required()
def get_room(room_code):
    room = Room.query.filter_by(room_code=room_code).first_or_404()
    return jsonify({
        "id": room.id,
        "room_code": room.room_code,
        "title": room.title,
        "host_id": room.host_id,
        "room_type": room.room_type,
        "is_active": room.is_active,
        "status": room.status,
        "is_locked": room.is_locked,
        "waiting_room_enabled": room.waiting_room_enabled,
        "security_flags_json": room.security_flags_json or '{}'
    }), 200

@rooms_bp.route('/<room_code>/join', methods=['POST'])
@jwt_required()
def join_room(room_code):
    user_id = get_jwt_identity()
    room = Room.query.filter_by(room_code=room_code, is_active=True).first_or_404()
    
    is_host = (user_id == room.host_id)

    if room.is_locked and not is_host:
        return jsonify({"error": "Room is locked"}), 403

    existing = RoomParticipant.query.filter_by(room_id=room.id, user_id=user_id).order_by(RoomParticipant.join_time.desc()).first()
    
    if existing and existing.status == 'blocked':
        return jsonify({"error": "You are blocked from this room"}), 403
        
    active_participant = RoomParticipant.query.filter_by(room_id=room.id, user_id=user_id, leave_time=None).first()
    
    participant_status = 'joined'
    if not is_host and room.waiting_room_enabled:
        participant_status = 'waiting'
        
    if not active_participant:
        participant = RoomParticipant(
            id=str(uuid.uuid4()),
            room_id=room.id,
            user_id=user_id,
            status=participant_status
        )
        db.session.add(participant)
        
        if participant_status == 'joined':
            # record attendance
            att = Attendance(
                id=str(uuid.uuid4()),
                user_id=user_id,
                room_id=room.id
            )
            db.session.add(att)
            
        db.session.commit()
    else:
        # If active_participant but was in waiting and host changed something or user retrying
        if active_participant.status != participant_status and participant_status == 'joined':
            active_participant.status = 'joined'
            att = Attendance(
                id=str(uuid.uuid4()),
                user_id=user_id,
                room_id=room.id
            )
            db.session.add(att)
            db.session.commit()
        participant_status = active_participant.status

    return jsonify({"message": "Joined" if participant_status == 'joined' else "Waiting for host", "status": participant_status, "room_id": room.id, "room_code": room.room_code}), 200

@rooms_bp.route('/<room_code>/leave', methods=['POST'])
@jwt_required()
def leave_room(room_code):
    user_id = get_jwt_identity()
    room = Room.query.filter_by(room_code=room_code).first_or_404()
    participant = RoomParticipant.query.filter_by(room_id=room.id, user_id=user_id, leave_time=None).first()
    if participant:
        participant.leave_time = datetime.utcnow()
        att = Attendance.query.filter_by(room_id=room.id, user_id=user_id, leave_time=None).first()
        if att:
            att.leave_time = datetime.utcnow()
            if att.join_time:
                att.total_duration_seconds = int((att.leave_time - att.join_time).total_seconds())
        db.session.commit()
    return jsonify({"message": "Left room"}), 200

@rooms_bp.route('/my', methods=['GET'])
@jwt_required()
def my_rooms():
    user_id = get_jwt_identity()
    hosted = Room.query.filter_by(host_id=user_id).all()
    return jsonify([{
        "id": r.id, "room_code": r.room_code,
        "title": r.title, "room_type": r.room_type, "is_active": r.is_active, "status": r.status
    } for r in hosted]), 200

@rooms_bp.route('/<room_id>/state', methods=['POST'])
@jwt_required()
def update_room_state(room_id):
    user_id = get_jwt_identity()
    data = request.get_json()
    room = Room.query.filter_by(id=room_id, host_id=user_id).first_or_404()
    
    if 'status' in data:
        status = data['status']
        if status in ['scheduled', 'active', 'paused', 'ended']:
            room.status = status
            if status == 'ended':
                room.is_active = False
                room.ended_at = datetime.utcnow()
                # end all attendances
                for p in RoomParticipant.query.filter_by(room_id=room.id, leave_time=None).all():
                    p.leave_time = datetime.utcnow()
                    att = Attendance.query.filter_by(room_id=room.id, user_id=p.user_id, leave_time=None).first()
                    if att:
                        att.leave_time = datetime.utcnow()
                        if att.join_time:
                            att.total_duration_seconds = int((att.leave_time - att.join_time).total_seconds())

    if 'is_locked' in data:
        room.is_locked = bool(data['is_locked'])
    if 'waiting_room_enabled' in data:
        room.waiting_room_enabled = bool(data['waiting_room_enabled'])

    db.session.commit()
    return jsonify({"message": "Room state updated", "status": room.status, "is_locked": room.is_locked, "waiting_room_enabled": room.waiting_room_enabled}), 200

@rooms_bp.route('/<room_id>/waiting', methods=['GET'])
@jwt_required()
def get_waiting_participants(room_id):
    user_id = get_jwt_identity()
    room = Room.query.filter_by(id=room_id, host_id=user_id).first_or_404()
    
    waiting = RoomParticipant.query.filter_by(room_id=room.id, status='waiting', leave_time=None).all()
    result = []
    for w in waiting:
        u = User.query.get(w.user_id)
        if u:
            result.append({"id": w.user_id, "name": u.name, "email": u.email})
            
    return jsonify(result), 200

@rooms_bp.route('/<room_id>/participants/<participant_id>/status', methods=['POST'])
@jwt_required()
def set_participant_status(room_id, participant_id):
    user_id = get_jwt_identity()
    data = request.get_json()
    new_status = data.get('status')
    
    if new_status not in ['approved', 'rejected']:
        return jsonify({"error": "Invalid status"}), 400

    room = Room.query.filter_by(id=room_id, host_id=user_id).first_or_404()
    participant = RoomParticipant.query.filter_by(room_id=room.id, user_id=participant_id, leave_time=None).first_or_404()
    
    participant.status = 'joined' if new_status == 'approved' else 'rejected'
    
    if new_status == 'approved':
        att = Attendance.query.filter_by(room_id=room.id, user_id=participant_id, leave_time=None).first()
        if not att:
            att = Attendance(
                id=str(uuid.uuid4()),
                user_id=participant_id,
                room_id=room.id
            )
            db.session.add(att)
            
    db.session.commit()
    return jsonify({"message": f"Participant {new_status}"}), 200

@rooms_bp.route('/<room_id>/participants/<participant_id>/block', methods=['POST'])
@jwt_required()
def block_participant(room_id, participant_id):
    user_id = get_jwt_identity()
    room = Room.query.filter_by(id=room_id, host_id=user_id).first_or_404()
    participant = RoomParticipant.query.filter_by(room_id=room.id, user_id=participant_id, leave_time=None).first()
    
    if participant:
        participant.status = 'blocked'
        participant.leave_time = datetime.utcnow()
        # end attendance
        att = Attendance.query.filter_by(room_id=room.id, user_id=participant_id, leave_time=None).first()
        if att:
            att.leave_time = datetime.utcnow()
            if att.join_time:
                att.total_duration_seconds = int((att.leave_time - att.join_time).total_seconds())
    else:
        # If they already left, just mark the most recent record as blocked or create a new blocked record
        last_record = RoomParticipant.query.filter_by(room_id=room.id, user_id=participant_id).order_by(RoomParticipant.join_time.desc()).first()
        if last_record:
            last_record.status = 'blocked'
        else:
            participant = RoomParticipant(id=str(uuid.uuid4()), room_id=room.id, user_id=participant_id, status='blocked')
            db.session.add(participant)
            
    db.session.commit()
    return jsonify({"message": "Participant blocked"}), 200

@rooms_bp.route('/<room_id>/attendance', methods=['GET'])
@jwt_required()
def get_attendance(room_id):
    user_id = get_jwt_identity()
    room = Room.query.filter_by(id=room_id, host_id=user_id).first_or_404()
    
    attendances = Attendance.query.filter_by(room_id=room.id).all()
    result = []
    for att in attendances:
        user = User.query.get(att.user_id)
        if user:
            result.append({
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "join_time": att.join_time.isoformat() if att.join_time else None,
                "leave_time": att.leave_time.isoformat() if att.leave_time else None,
                "duration_seconds": att.total_duration_seconds or 0,
                "face_check_passed": att.face_check_passed
            })
            
    return jsonify(result), 200


@rooms_bp.route('/<room_id>/participants/live', methods=['GET'])
@jwt_required()
def get_live_participants(room_id):
    """Returns currently-joined (active) participants for the host's live monitoring panel."""
    user_id = get_jwt_identity()
    room = Room.query.filter_by(id=room_id, host_id=user_id).first_or_404()

    active = RoomParticipant.query.filter_by(room_id=room.id, status='joined', leave_time=None).all()
    result = []
    for p in active:
        u = User.query.get(p.user_id)
        if u:
            att = Attendance.query.filter_by(room_id=room.id, user_id=p.user_id, leave_time=None).first()
            result.append({
                "id": p.user_id,
                "name": u.name,
                "email": u.email,
                "join_time": att.join_time.isoformat() if att and att.join_time else p.join_time.isoformat() if p.join_time else None,
                "face_check_passed": att.face_check_passed if att else None
            })

    return jsonify(result), 200

@rooms_bp.route('/my-attended', methods=['GET'])
@jwt_required()
def my_attended_rooms():
    user_id = get_jwt_identity()
    attendances = Attendance.query.filter_by(user_id=user_id).order_by(Attendance.join_time.desc()).all()
    room_ids = []
    unique_rooms = []
    for att in attendances:
        if att.room_id not in room_ids:
            room_ids.append(att.room_id)
            room = Room.query.get(att.room_id)
            if room:
                unique_rooms.append({
                    "id": room.id,
                    "title": room.title,
                    "room_code": room.room_code,
                    "room_type": room.room_type,
                    "status": room.status,
                    "attended_at": att.join_time.isoformat() if att.join_time else None
                })
    return jsonify(unique_rooms), 200

@rooms_bp.route('/<room_id>/materials', methods=['GET'])
@jwt_required()
def get_room_materials(room_id):
    user_id = get_jwt_identity()
    room = Room.query.get_or_404(room_id)
    
    if room.host_id != user_id:
        att = Attendance.query.filter_by(room_id=room_id, user_id=user_id).first()
        if not att:
            return jsonify({"error": "Access denied"}), 403

    lecture = LectureRecord.query.filter_by(room_id=room_id).first()
    materials = {
        "has_summary": False,
        "ai_lecture_id": None,
        "summary": None,
        "key_points": None,
        "important_topics": None,
        "has_recording": False,
        "recording_file": None
    }
    
    if lecture:
        ai_lec = AILecture.query.filter_by(lecture_id=lecture.id).first()
        if ai_lec and ai_lec.processing_status == 'done':
            materials["has_summary"] = True
            materials["ai_lecture_id"] = str(ai_lec.id)
            materials["summary"] = ai_lec.summary
            materials["key_points"] = ai_lec.key_points
            materials["important_topics"] = ai_lec.important_topics

    try:
        flags = json.loads(room.security_flags_json or '{}')
        shared_ids = flags.get('shared_material_ids', [])
        # Backward compat: legacy single recording
        legacy_id = flags.get('shared_recording_id')
        if legacy_id and legacy_id not in shared_ids:
            shared_ids.append(legacy_id)
        if shared_ids:
            materials["has_recording"] = True
            shared_files = []
            for sid in shared_ids:
                cf = CloudFile.query.get(sid)
                if cf:
                    ext = cf.filename.rsplit('.', 1)[-1].lower() if '.' in cf.filename else ''
                    shared_files.append({
                        "id": cf.id,
                        "filename": cf.filename,
                        "size": cf.file_size,
                        "type": ext
                    })
            materials["shared_files"] = shared_files
            # Keep legacy field for old clients
            if shared_files:
                materials["recording_file"] = shared_files[0]
    except:
        pass
        
    return jsonify(materials), 200

@rooms_bp.route('/<room_id>/share-recording', methods=['PATCH'])
@jwt_required()
def share_recording(room_id):
    """Kept for backward compat — delegates to share-materials."""
    user_id = get_jwt_identity()
    room = Room.query.filter_by(id=room_id, host_id=user_id).first_or_404()
    data = request.get_json()
    file_id = data.get('file_id')
    try:
        flags = json.loads(room.security_flags_json or '{}')
    except:
        flags = {}
    existing = flags.get('shared_material_ids', [])
    if file_id and file_id not in existing:
        existing.append(file_id)
    flags['shared_material_ids'] = existing
    room.security_flags_json = json.dumps(flags)
    db.session.commit()
    return jsonify({"message": "Material shared"}), 200

@rooms_bp.route('/<room_id>/share-materials', methods=['PATCH'])
@jwt_required()
def share_materials(room_id):
    """Set the full list of shared material file IDs for a room."""
    user_id = get_jwt_identity()
    room = Room.query.filter_by(id=room_id, host_id=user_id).first_or_404()
    data = request.get_json()
    file_ids = data.get('file_ids', [])  # list of CloudFile IDs
    try:
        flags = json.loads(room.security_flags_json or '{}')
    except:
        flags = {}
    flags['shared_material_ids'] = file_ids
    room.security_flags_json = json.dumps(flags)
    
    # Notify guests who attended
    attendees = Attendance.query.filter_by(room_id=room.id).all()
    user_ids = list(set([a.user_id for a in attendees if a.user_id]))
    for uid in user_ids:
        if uid != user_id:
            n = Notification(
                user_id=uid,
                title="New Material Shared",
                message=f"Host shared {len(file_ids)} material(s) for {room.title}.",
                type="info"
            )
            db.session.add(n)

    db.session.commit()
    # Notify guests via socket
    from extensions import socketio as sio
    sio.emit('materials_shared', {'room_id': room_id, 'count': len(file_ids)},
             namespace='/conference', room=room.room_code)
    return jsonify({"message": "Materials updated", "count": len(file_ids)}), 200

