from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.ai_teaching import LectureRecord, AILecture, AITranslation, AIQuestion
from services.ai_teaching_service import (
    clean_transcript, generate_summary, translate_summary,
    generate_questions, extract_pdf_text, SUPPORTED_LANGUAGES
)
from extensions import db
import uuid, time, json

ai_bp = Blueprint('ai_teaching', __name__)

def safe_json_loads(val):
    if not val:
        return []
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val


@ai_bp.route('/record-lecture', methods=['POST'])
@jwt_required()
def record_lecture():
    data = request.get_json()
    transcript = data.get('transcript', '').strip()
    
    if not transcript or len(transcript) < 50:
        return jsonify({'error': 'Transcript too short (minimum 50 characters)'}), 400
    
    user_id = get_jwt_identity()
    cleaned = clean_transcript(transcript)
    
    record = LectureRecord(
        room_id=data.get('room_id'),
        teacher_id=user_id,
        title=data.get('title', 'Untitled Lecture'),
        transcript=cleaned,
        source=data.get('source', 'recording'),
        duration_seconds=data.get('duration_seconds'),
        word_count=len(cleaned.split())
    )
    db.session.add(record)
    db.session.commit()
    
    return jsonify({'lecture_id': str(record.id), 'word_count': record.word_count}), 201

@ai_bp.route('/summarize', methods=['POST'])
@jwt_required()
def summarize():
    data = request.get_json()
    lecture_id = data.get('lecture_id')
    
    lecture = LectureRecord.query.get_or_404(lecture_id)
    
    existing = AILecture.query.filter_by(lecture_id=lecture_id).first()
    if existing and existing.processing_status == 'done':
        return jsonify({
            'ai_lecture_id': str(existing.id),
            'summary': existing.summary,
            'key_points': safe_json_loads(existing.key_points),
            'important_topics': safe_json_loads(existing.important_topics),
            'keywords': safe_json_loads(existing.keywords),
            'cached': True
        })
    
    result = generate_summary(lecture.transcript)
    
    ai_lec = AILecture(
        lecture_id=lecture_id,
        summary=result['summary'],
        key_points=json.dumps(result['key_points']),
        important_topics=json.dumps(result['important_topics']),
        keywords=json.dumps(result['keywords']),
        processing_status='done',
        processing_time_ms=result['processing_time_ms']
    )
    db.session.add(ai_lec)
    db.session.commit()
    
    return jsonify({
        'ai_lecture_id': str(ai_lec.id),
        'summary': ai_lec.summary,
        'key_points': safe_json_loads(ai_lec.key_points),
        'important_topics': safe_json_loads(ai_lec.important_topics),
        'keywords': safe_json_loads(ai_lec.keywords),
        'processing_time_ms': result['processing_time_ms'],
        'cached': False
    })


@ai_bp.route('/translate', methods=['POST'])
@jwt_required()
def translate():
    data = request.get_json()
    ai_lecture_id = data.get('ai_lecture_id')
    target_lang = data.get('target_language', 'en')
    
    if target_lang not in SUPPORTED_LANGUAGES:
        return jsonify({'error': f'Unsupported language. Supported: {list(SUPPORTED_LANGUAGES.keys())}'}), 400
    
    ai_lec = AILecture.query.get_or_404(ai_lecture_id)
    
    cached = AITranslation.query.filter_by(ai_lecture_id=ai_lecture_id, target_language=target_lang).first()
    if cached:
        return jsonify({
            'translated_summary': cached.translated_summary,
            'translated_key_points': safe_json_loads(cached.translated_key_points),
            'language': target_lang,
            'language_name': SUPPORTED_LANGUAGES[target_lang],
            'cached': True
        })
    
    key_points_list = safe_json_loads(ai_lec.key_points)
    result = translate_summary(ai_lec.summary, key_points_list, target_lang)
    
    translation = AITranslation(
        ai_lecture_id=ai_lecture_id,
        target_language=target_lang,
        translated_summary=result['summary'],
        translated_key_points=json.dumps(result['key_points'])
    )
    db.session.add(translation)
    db.session.commit()
    
    return jsonify({
        'translated_summary': result['summary'],
        'translated_key_points': result['key_points'],
        'language': target_lang,
        'language_name': SUPPORTED_LANGUAGES[target_lang],
        'cached': False
    })


@ai_bp.route('/languages', methods=['GET'])
def get_languages():
    return jsonify({'languages': SUPPORTED_LANGUAGES})

@ai_bp.route('/generate-questions', methods=['POST'])
@jwt_required()
def generate_exam_questions():
    data = request.get_json()
    lecture_id = data.get('lecture_id')
    count = min(int(data.get('count', 5)), 20)
    q_type = data.get('type', 'mixed')
    difficulty = data.get('difficulty', 'medium')
    
    if q_type not in ('mcq', 'short_answer', 'mixed'):
        return jsonify({'error': 'type must be: mcq, short_answer, or mixed'}), 400
    
    lecture = LectureRecord.query.get_or_404(lecture_id)
    ai_lec = AILecture.query.filter_by(lecture_id=lecture_id).first()
    
    if not ai_lec:
        summary_result = generate_summary(lecture.transcript)
        ai_lec = AILecture(
            lecture_id=lecture_id,
            summary=summary_result['summary'],
            key_points=json.dumps(summary_result['key_points']),
            important_topics=json.dumps(summary_result['important_topics']),
            keywords=json.dumps(summary_result['keywords']),
            processing_status='done',
            processing_time_ms=summary_result['processing_time_ms']
        )
        db.session.add(ai_lec)
        db.session.flush()
    
    key_points_list = safe_json_loads(ai_lec.key_points)
    questions = generate_questions(
        transcript=lecture.transcript,
        summary=ai_lec.summary,
        key_points=key_points_list,
        count=count,
        q_type=q_type,
        difficulty=difficulty
    )
    
    record = AIQuestion(
        lecture_id=lecture_id,
        ai_lecture_id=str(ai_lec.id),
        question_type=q_type,
        question_count=len(questions),
        questions_json=json.dumps(questions),
        difficulty=difficulty
    )
    db.session.add(record)
    db.session.commit()
    
    return jsonify({
        'question_set_id': str(record.id),
        'questions': questions,
        'question_count': len(questions),
        'type': q_type,
        'difficulty': difficulty
    })


@ai_bp.route('/upload-pdf', methods=['POST'])
@jwt_required()
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are supported'}), 400
    
    file_bytes = file.read()
    try:
        extracted_text = extract_pdf_text(file_bytes)
    except ValueError as e:
        return jsonify({'error': str(e)}), 422
    
    user_id = get_jwt_identity()
    title = request.form.get('title') or file.filename.replace('.pdf', '')
    
    record = LectureRecord(
        room_id=request.form.get('room_id'),
        teacher_id=user_id,
        title=title,
        transcript=extracted_text,
        source='pdf',
        original_filename=file.filename,
        word_count=len(extracted_text.split())
    )
    db.session.add(record)
    db.session.commit()
    
    return jsonify({'lecture_id': str(record.id), 'word_count': record.word_count, 'title': title, 'source': 'pdf'}), 201

@ai_bp.route('/lectures', methods=['GET'])
@jwt_required()
def list_lectures():
    user_id = get_jwt_identity()
    lectures = LectureRecord.query.filter_by(teacher_id=user_id).order_by(LectureRecord.created_at.desc()).all()
    return jsonify({'lectures': [{
        'id': str(l.id),
        'title': l.title,
        'source': l.source,
        'word_count': l.word_count,
        'created_at': l.created_at.isoformat(),
        'has_summary': AILecture.query.filter_by(lecture_id=l.id).count() > 0
    } for l in lectures]})

@ai_bp.route('/lectures/<lecture_id>/summary', methods=['GET'])
@jwt_required()
def get_lecture_summary(lecture_id):
    ai_lec = AILecture.query.filter_by(lecture_id=lecture_id).first_or_404()
    questions = AIQuestion.query.filter_by(lecture_id=lecture_id).order_by(AIQuestion.created_at.desc()).first()
    
    return jsonify({
        'summary': ai_lec.summary,
        'key_points': safe_json_loads(ai_lec.key_points),
        'important_topics': safe_json_loads(ai_lec.important_topics),
        'keywords': safe_json_loads(ai_lec.keywords),
        'questions': safe_json_loads(questions.questions_json) if questions else []
    })

