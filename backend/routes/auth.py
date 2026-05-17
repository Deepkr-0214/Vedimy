from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from models import User, SecurityLog, AuthHistory
from extensions import socketio
from extensions import db, bcrypt, limiter
import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    data = request.get_json()
    if User.query.filter_by(email=data.get('email')).first():
        return jsonify({"error": "Email already exists"}), 400
    
    image_base64 = data.get('image')
    if not image_base64:
        return jsonify({"error": "Face biometric image is required"}), 400
        
    try:
        from services import face_service
        import pickle
        encoding = face_service.encode_face(image_base64)
    except Exception as e:
        return jsonify({"error": f"Face detection failed: Ensure your face is clearly visible."}), 400

    hashed = bcrypt.generate_password_hash(data.get('password')).decode('utf-8')
    user = User(
        name=data.get('name'),
        email=data.get('email'),
        password_hash=hashed,
        role=data.get('role', 'guest'),
        face_encoding=pickle.dumps(encoding),
        face_registered=True
    )
    db.session.add(user)
    db.session.commit()
    
    return jsonify({"message": "User registered successfully", "user_id": str(user.id)}), 201

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data.get('email')).first()
    
    if user and user.role == data.get('role') and bcrypt.check_password_hash(user.password_hash, data.get('password')):
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        user.last_login = datetime.datetime.utcnow()
        
        # Log authentication history
        log = AuthHistory(
            user_id=str(user.id),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            auth_method='password',
            status='success'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "face_registered": user.face_registered
            }
        }), 200
        
    # Log failed attempt if user exists
    if user:
        log = AuthHistory(
            user_id=str(user.id),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            auth_method='password',
            status='failed'
        )
        db.session.add(log)
        db.session.commit()

    return jsonify({"error": "Invalid email or password"}), 401

@auth_bp.route('/login/face', methods=['POST'])
@limiter.limit("5 per minute")
def login_face():
    data = request.get_json()
    email = data.get('email')
    role = data.get('role')
    image_base64 = data.get('image')

    user = User.query.filter_by(email=email, role=role).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    if not user.face_registered or not user.face_encoding:
        return jsonify({"error": "Face not registered for this user"}), 400

    if not image_base64:
        return jsonify({"error": "Face image is required"}), 400

    try:
        from services import face_service
        import pickle
        stored_encoding = pickle.loads(user.face_encoding)
        res = face_service.verify_face(image_base64, stored_encoding)
        
        if res.get("match"):
            access_token = create_access_token(identity=str(user.id))
            refresh_token = create_refresh_token(identity=str(user.id))
            user.last_login = datetime.datetime.utcnow()
            
            # Log authentication history
            log = AuthHistory(
                user_id=str(user.id),
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                auth_method='face',
                status='success'
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": {
                    "id": str(user.id),
                    "name": user.name,
                    "email": user.email,
                    "role": user.role,
                    "face_registered": user.face_registered
                }
            }), 200
        else:
            # Log failed face attempt
            log = AuthHistory(
                user_id=str(user.id),
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                auth_method='face',
                status='failed'
            )
            db.session.add(log)
            db.session.commit()
            return jsonify({"error": "Face verification failed"}), 401
    except Exception as e:
        return jsonify({"error": "Error verifying face"}), 500


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    return jsonify({
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "face_registered": user.face_registered
    }), 200

@auth_bp.route('/profile/name', methods=['PUT'])
@jwt_required()
def change_name():
    user_id = get_jwt_identity()
    data = request.get_json()
    new_name = data.get('name')
    if not new_name:
        return jsonify({"error": "Name is required"}), 400
        
    user = User.query.get(user_id)
    old_name = user.name
    user.name = new_name
    
    # Log the change
    log = SecurityLog(
        user_id=user.id,
        event_type='name_change',
        details={'old_name': old_name, 'new_name': new_name, 'email': user.email}
    )
    db.session.add(log)
    db.session.commit()
    
    # Broadcast to conference and proctoring
    payload = {
        'user_id': user.id,
        'old_name': old_name,
        'new_name': new_name,
        'email': user.email
    }
    socketio.emit('name_changed', payload, namespace='/conference')
    socketio.emit('name_changed', payload, namespace='/proctoring')
    socketio.emit('name_changed', payload, namespace='/coordinator')
    
    return jsonify({"message": "Name updated", "name": new_name}), 200
