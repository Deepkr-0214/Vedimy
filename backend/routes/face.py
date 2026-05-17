from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User
from extensions import db
from services import face_service
import pickle

face_bp = Blueprint('face', __name__)

@face_bp.route('/register', methods=['POST'])
@jwt_required()
def register_face():
    data = request.get_json()
    image_base64 = data.get('image')
    
    if not image_base64:
        return jsonify({"error": "No image provided"}), 400
        
    try:
        encoding = face_service.encode_face(image_base64)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
        
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    # Store encoding as pickled bytes
    user.face_encoding = pickle.dumps(encoding)
    user.face_registered = True
    db.session.commit()
    
    return jsonify({"message": "Face registered successfully"}), 200

@face_bp.route('/verify', methods=['POST'])
@jwt_required()
def verify_face():
    data = request.get_json()
    image_base64 = data.get('image')
    
    if not image_base64:
        return jsonify({"error": "No image provided"}), 400
        
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user.face_registered or not user.face_encoding:
        return jsonify({"error": "Face not registered"}), 400
        
    stored_encoding = pickle.loads(user.face_encoding)
    
    try:
        result = face_service.verify_face(image_base64, stored_encoding)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@face_bp.route('/delete', methods=['DELETE'])
@jwt_required()
def delete_face():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    user.face_encoding = None
    user.face_registered = False
    db.session.commit()
    
    return jsonify({"message": "Biometric data permanently deleted"}), 200
