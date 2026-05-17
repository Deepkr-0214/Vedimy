import os
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from extensions import db
from models import CloudFile

files_bp = Blueprint('files', __name__)

UPLOAD_FOLDER = os.path.join('static', 'uploads', 'host_files')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@files_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_file():
    host_id = get_jwt_identity()
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400
        
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        cloud_file = CloudFile(
            host_id=host_id,
            filename=filename,
            file_path=file_path,
            file_type=file.content_type,
            file_size=os.path.getsize(file_path)
        )
        db.session.add(cloud_file)
        db.session.commit()
        
        return jsonify({
            "message": "File uploaded successfully",
            "file": {"id": cloud_file.id, "filename": cloud_file.filename}
        }), 201

@files_bp.route('/list', methods=['GET'])
@jwt_required()
def list_files():
    host_id = get_jwt_identity()
    files = CloudFile.query.filter_by(host_id=host_id).order_by(CloudFile.uploaded_at.desc()).all()
    
    return jsonify([{
        "id": f.id,
        "filename": f.filename,
        "file_type": f.file_type,
        "file_size": f.file_size,
        "uploaded_at": f.uploaded_at.isoformat()
    } for f in files]), 200

@files_bp.route('/download/<file_id>', methods=['GET'])
@jwt_required()
def download_file(file_id):
    host_id = get_jwt_identity()
    file_record = CloudFile.query.filter_by(id=file_id, host_id=host_id).first_or_404()
    
    return send_from_directory(
        os.path.abspath(os.path.dirname(file_record.file_path)),
        os.path.basename(file_record.file_path),
        as_attachment=True
    )
