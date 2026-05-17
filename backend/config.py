import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'vedimy-dev-secret-2024')
    
    # SQLite — zero external dependencies
    _db_url = os.environ.get('DATABASE_URL', 'sqlite:///vedimy.db')
    # Normalize postgres:// for compatibility
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False}  # Required for SQLite
    }
    
    # JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'vedimy-jwt-secret-2024')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@vedimy.com')
    
    # App Settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    FACE_MATCH_THRESHOLD = float(os.environ.get('FACE_MATCH_THRESHOLD', 0.5))
    MAX_VIOLATIONS_BEFORE_TERMINATE = 3
    SCREENSHOT_DIR = 'static/screenshots'
    REPORTS_DIR = 'static/reports'
    FACE_ENCRYPTION_KEY = os.environ.get('FACE_ENCRYPTION_KEY', 'x' * 32)

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///vedimy_dev.db'

class ProductionConfig(Config):
    DEBUG = False
    # On Railway with Volume: DATABASE_URL=sqlite:////data/vedimy.db
