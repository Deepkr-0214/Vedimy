import os
import sqlite3
from flask import Flask, jsonify, send_from_directory, abort
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from config import Config
from extensions import db, migrate, jwt, socketio, cors, mail, bcrypt, limiter

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={
        r"/api/*": {"origins": "*"},
        r"/socket.io/*": {"origins": "*"}
    })
    mail.init_app(app)
    bcrypt.init_app(app)
    limiter.init_app(app)
    socketio.init_app(app)

    # Make static dirs if they don't exist
    os.makedirs(app.config['SCREENSHOT_DIR'], exist_ok=True)
    os.makedirs(app.config['REPORTS_DIR'], exist_ok=True)

    # Register Blueprints
    from routes.auth import auth_bp
    from routes.rooms import rooms_bp
    from routes.exams import exams_bp
    from routes.face import face_bp
    from routes.coordinator import coordinator_bp
    from routes.ai_teaching import ai_bp
    from routes.analytics import analytics_bp
    from routes.files import files_bp
    from routes.guest_face import guest_face_bp
    from routes.guest_registration import guest_reg_bp
    from routes.notifications import notif_bp
    from routes.chatbot import chatbot_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(rooms_bp, url_prefix='/api/rooms')
    app.register_blueprint(exams_bp, url_prefix='/api/exams')
    app.register_blueprint(face_bp, url_prefix='/api/face')
    app.register_blueprint(coordinator_bp, url_prefix='/api/coordinator')
    app.register_blueprint(ai_bp, url_prefix='/api/ai')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    app.register_blueprint(files_bp, url_prefix='/api/files')
    app.register_blueprint(guest_face_bp, url_prefix='/api/guest-face')
    app.register_blueprint(guest_reg_bp,  url_prefix='/api/guest-reg')
    app.register_blueprint(notif_bp, url_prefix='/api/notifications')
    app.register_blueprint(chatbot_bp, url_prefix='/api/chatbot')

    import sockets

    @app.route('/api/health')
    def health():
        return jsonify({"status": "healthy"}), 200

    @app.route('/api/files/screenshots/<filename>')
    def serve_screenshot(filename):
        return send_from_directory(app.config['SCREENSHOT_DIR'], filename)

    # Error handlers
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "Bad Request", "message": str(error)}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({"error": "Unauthorized", "message": str(error)}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({"error": "Forbidden", "message": str(error)}), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not Found", "message": str(error)}), 404

    @app.errorhandler(500)
    def server_error(error):
        return jsonify({"error": "Internal Server Error", "message": str(error)}), 500

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        if path.startswith('api/') or path.startswith('socket.io/'):
            abort(404)
        frontend_dir = os.path.join(app.root_path, '..', 'frontend')
        if path and os.path.exists(os.path.join(frontend_dir, path)):
            return send_from_directory(frontend_dir, path)
        return send_from_directory(os.path.join(frontend_dir, 'pages'), 'index.html')

    return app

if __name__ == '__main__':
    app = create_app()
    socketio.run(app, debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
