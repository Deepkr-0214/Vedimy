from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import CoordinatorLog, Exam, User, Violation
from extensions import db
import uuid
from datetime import datetime

coordinator_bp = Blueprint('coordinator', __name__)

@coordinator_bp.route('/exams', methods=['GET'])
@jwt_required()
def my_exams():
    user_id = get_jwt_identity()
    # Exam model uses host_id — coordinators can view exams they host
    exams = Exam.query.filter_by(host_id=user_id).all()
    return jsonify([{
        "id": str(e.id),
        "title": e.title,
        "status": e.status,
        "duration_minutes": e.duration_minutes,
        "start_time": e.start_time.isoformat() if e.start_time else None
    } for e in exams]), 200

@coordinator_bp.route('/monitor/<exam_id>', methods=['GET'])
@jwt_required()
def monitor_exam(exam_id):
    violations = Violation.query.filter_by(exam_id=exam_id).all()
    return jsonify({
        "exam_id": exam_id,
        "violation_count": len(violations),
        "violations": [{
            "user_id": v.user_id,
            "type": v.violation_type,
            "severity": v.severity,
            "timestamp": v.timestamp.isoformat(),
            "screenshot": v.screenshot_path
        } for v in violations]
    }), 200

@coordinator_bp.route('/action', methods=['POST'])
@jwt_required()
def take_action():
    data = request.get_json()
    coord_id = get_jwt_identity()
    log = CoordinatorLog(
        id=str(uuid.uuid4()),
        coordinator_id=coord_id,
        exam_id=data.get('exam_id'),
        action_type=data.get('action_type', 'manual'),
        target_user_id=data.get('target_user_id'),
        notes=data.get('notes', '')
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({"message": "Action logged", "log_id": log.id}), 200

@coordinator_bp.route('/logs', methods=['GET'])
@jwt_required()
def get_logs():
    coord_id = get_jwt_identity()
    logs = CoordinatorLog.query.filter_by(coordinator_id=coord_id).order_by(CoordinatorLog.timestamp.desc()).limit(50).all()
    return jsonify([{
        "id": l.id,
        "action_type": l.action_type,
        "target_user_id": l.target_user_id,
        "notes": l.notes,
        "timestamp": l.timestamp.isoformat()
    } for l in logs]), 200
