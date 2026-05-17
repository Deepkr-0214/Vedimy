from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import Exam, Room, Attendance, Violation
from extensions import db
import uuid
from datetime import datetime

exams_bp = Blueprint('exams', __name__)

@exams_bp.route('/create', methods=['POST'])
@jwt_required()
def create_exam():
    data = request.get_json()
    user_id = get_jwt_identity()
    exam = Exam(
        id=str(uuid.uuid4()),
        room_id=data.get('room_id'),
        title=data.get('title', 'Untitled Exam'),
        description=data.get('description', ''),
        host_id=user_id,
        duration_minutes=data.get('duration_minutes', 60),
        max_warnings=data.get('max_warnings', 3),
        face_check_interval=data.get('face_check_interval', 10)
    )
    db.session.add(exam)
    db.session.commit()
    return jsonify({"id": exam.id, "title": exam.title}), 201

@exams_bp.route('/<exam_id>', methods=['GET'])
@jwt_required()
def get_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    return jsonify({
        "id": exam.id,
        "title": exam.title,
        "description": exam.description,
        "duration_minutes": exam.duration_minutes,
        "status": exam.status,
        "start_time": exam.start_time.isoformat() if exam.start_time else None,
        "max_warnings": exam.max_warnings,
        "instructions": exam.instructions,
        "questions": exam.questions_json
    }), 200

@exams_bp.route('/<exam_id>/start', methods=['PUT'])
@jwt_required()
def start_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    exam.status = 'active'
    exam.start_time = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "Exam started", "start_time": exam.start_time.isoformat()}), 200

@exams_bp.route('/<exam_id>/end', methods=['PUT'])
@jwt_required()
def end_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    exam.status = 'ended'
    exam.end_time = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "Exam ended"}), 200

@exams_bp.route('/<exam_id>/violations', methods=['GET'])
@jwt_required()
def get_violations(exam_id):
    violations = Violation.query.filter_by(exam_id=exam_id).all()
    return jsonify([{
        "id": v.id,
        "user_id": v.user_id,
        "violation_type": v.violation_type,
        "severity": v.severity,
        "warning_count": v.warning_count,
        "timestamp": v.timestamp.isoformat()
    } for v in violations]), 200

@exams_bp.route('/<exam_id>/attendance', methods=['GET'])
@jwt_required()
def get_attendance(exam_id):
    records = Attendance.query.filter_by(exam_id=exam_id).all()
    return jsonify([{
        "id": a.id,
        "user_id": a.user_id,
        "status": a.status,
        "join_time": a.join_time.isoformat() if a.join_time else None,
        "leave_time": a.leave_time.isoformat() if a.leave_time else None
    } for a in records]), 200

@exams_bp.route('/upcoming', methods=['GET'])
@jwt_required()
def upcoming_exams():
    now = datetime.utcnow()
    exams = Exam.query.filter(Exam.status == 'scheduled').all()
    return jsonify([{
        "id": e.id,
        "title": e.title,
        "duration_minutes": e.duration_minutes,
        "start_time": e.start_time.isoformat() if e.start_time else None
    } for e in exams]), 200

@exams_bp.route('/<exam_id>/questions', methods=['PUT'])
@jwt_required()
def attach_questions(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    data = request.get_json()
    exam.questions_json = data.get('questions')
    db.session.commit()
    return jsonify({"message": "Questions attached successfully"}), 200

@exams_bp.route('/<exam_id>/submit', methods=['POST'])
@jwt_required()
def submit_exam(exam_id):
    from models import ExamSubmission
    import json as json_lib
    user_id = get_jwt_identity()
    data = request.get_json()
    answers = data.get('answers', {})
    exam = Exam.query.get_or_404(exam_id)

    # Auto-grade MCQ answers
    score = None
    try:
        questions = exam.questions_json or []
        if isinstance(questions, str):
            questions = json_lib.loads(questions)
        if questions:
            correct = 0
            graded = 0
            for i, q in enumerate(questions):
                key = f"q_{i}"
                if q.get('type') == 'mcq' and 'correct_answer' in q:
                    graded += 1
                    if answers.get(key, '').strip().upper() == str(q['correct_answer']).strip().upper():
                        correct += 1
                elif q.get('type') in ('short_answer', 'subjective'):
                    graded += 1
                    if answers.get(key, '').strip():
                        correct += 0.5  # partial credit for attempted subjective
            score = round((correct / graded) * 100, 1) if graded > 0 else 0.0
    except Exception:
        score = None

    submission = ExamSubmission(
        exam_id=exam_id,
        user_id=user_id,
        answers_json=answers,
        score=score
    )
    db.session.add(submission)
    db.session.commit()
    return jsonify({"message": "Exam submitted successfully", "score": score}), 201

@exams_bp.route('/my-results', methods=['GET'])
@jwt_required()
def my_results():
    from models import ExamSubmission
    user_id = get_jwt_identity()
    subs = ExamSubmission.query.filter_by(user_id=user_id).order_by(ExamSubmission.submitted_at.desc()).all()
    results = []
    for s in subs:
        exam = Exam.query.get(s.exam_id)
        room = Room.query.get(exam.room_id) if exam else None
        results.append({
            "submission_id": s.id,
            "exam_id": s.exam_id,
            "exam_title": exam.title if exam else "Unknown",
            "room_title": room.title if room else "Unknown",
            "score": s.score,
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None
        })
    return jsonify(results), 200
