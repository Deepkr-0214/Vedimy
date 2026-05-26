from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import Room, RoomParticipant, ExamSubmission, SecurityLog, AuthHistory, Attendance, BiometricVerificationLog, User

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_stats():
    host_id = get_jwt_identity()
    
    # Total classes hosted by this host
    total_classes = Room.query.filter_by(host_id=host_id).count()
    
    # Total students who joined rooms hosted by this host
    total_students = db.session.query(RoomParticipant).join(Room).filter(Room.host_id == host_id).count()
    
    # Violation counts (using event_type column from SecurityLog)
    violations_raw = db.session.query(SecurityLog.event_type, db.func.count(SecurityLog.id)).\
        join(Room, SecurityLog.room_id == Room.id).filter(Room.host_id == host_id).\
        group_by(SecurityLog.event_type).all()
    
    violation_stats = {v[0]: v[1] for v in violations_raw}
    
    # Exam submissions count
    total_exams = ExamSubmission.query.join(Room, ExamSubmission.exam_id == Room.id).filter(Room.host_id == host_id).count()
    
    return jsonify({
        "total_classes": total_classes,
        "total_students": total_students,
        "violations": violation_stats,
        "total_exams_submitted": total_exams
    }), 200
    
@analytics_bp.route('/security-activity', methods=['GET'])
@jwt_required()
def get_security_activity():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    # 1. Biometric verification logs
    biometric_logs = BiometricVerificationLog.query.filter_by(user_id=user_id).order_by(BiometricVerificationLog.timestamp.desc()).limit(50).all()
    
    # 2. Session authentication history
    auth_logs = AuthHistory.query.filter_by(user_id=user_id).order_by(AuthHistory.timestamp.desc()).limit(50).all()
    
    # 3. Attendance logs
    attendance_logs = Attendance.query.filter_by(user_id=user_id).order_by(Attendance.join_time.desc()).limit(50).all()
    
    # 4. Security monitoring activity (violations)
    security_logs = SecurityLog.query.filter_by(user_id=user_id).order_by(SecurityLog.timestamp.desc()).limit(50).all()
    
    return jsonify({
        "biometric_logs": [{
            "id": l.id,
            "result": l.result,
            "confidence": l.confidence,
            "timestamp": l.timestamp.isoformat()
        } for l in biometric_logs],
        "auth_logs": [{
            "id": l.id,
            "ip_address": l.ip_address,
            "user_agent": l.user_agent,
            "auth_method": l.auth_method,
            "status": l.status,
            "timestamp": l.timestamp.isoformat()
        } for l in auth_logs],
        "attendance_logs": [{
            "id": l.id,
            "room_id": l.room_id,
            "room_title": Room.query.get(l.room_id).title if l.room_id and Room.query.get(l.room_id) else "Unknown Session",
            "room_code":  Room.query.get(l.room_id).room_code if l.room_id and Room.query.get(l.room_id) else "",
            "room_type":  Room.query.get(l.room_id).room_type if l.room_id and Room.query.get(l.room_id) else "class",
            "join_time": l.join_time.isoformat() if l.join_time else None,
            "leave_time": l.leave_time.isoformat() if l.leave_time else None,
            "status": l.status
        } for l in attendance_logs],
        "security_logs": [{
            "id": l.id,
            "event_type": l.event_type,
            "details": l.details,
            "timestamp": l.timestamp.isoformat()
        } for l in security_logs]
    }), 200

@analytics_bp.route('/attendance-trend', methods=['GET'])
@jwt_required()
def get_attendance_trend():
    host_id = get_jwt_identity()
    
    # Get attendance counts grouped by date for host's rooms
    # Since sqlite doesn't have a simple date() grouping across dialects in sqlalchemy,
    # we'll fetch recent attendances and group in python
    attendances = db.session.query(Attendance.join_time).join(Room, Attendance.room_id == Room.id).filter(Room.host_id == host_id, Attendance.join_time.isnot(None)).all()
    
    trend = {}
    for a in attendances:
        date_str = a.join_time.strftime('%Y-%m-%d')
        trend[date_str] = trend.get(date_str, 0) + 1
        
    # Sort by date
    sorted_trend = sorted([{"date": k, "count": v} for k, v in trend.items()], key=lambda x: x["date"])[-14:] # Last 14 days with data
    
    return jsonify(sorted_trend), 200

@analytics_bp.route('/exam-scores', methods=['GET'])
@jwt_required()
def get_exam_scores():
    host_id = get_jwt_identity()
    
    submissions = db.session.query(ExamSubmission.score).join(Room, ExamSubmission.exam_id == Room.id).filter(Room.host_id == host_id, ExamSubmission.score.isnot(None)).all()
    
    ranges = {
        "0-20": 0,
        "21-40": 0,
        "41-60": 0,
        "61-80": 0,
        "81-100": 0
    }
    
    for s in submissions:
        score = s.score
        if score <= 20: ranges["0-20"] += 1
        elif score <= 40: ranges["21-40"] += 1
        elif score <= 60: ranges["41-60"] += 1
        elif score <= 80: ranges["61-80"] += 1
        else: ranges["81-100"] += 1
        
    return jsonify([
        {"range": "0-20", "count": ranges["0-20"]},
        {"range": "21-40", "count": ranges["21-40"]},
        {"range": "41-60", "count": ranges["41-60"]},
        {"range": "61-80", "count": ranges["61-80"]},
        {"range": "81-100", "count": ranges["81-100"]}
    ]), 200
