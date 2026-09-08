from flask import Flask
from .course_routes import course_bp
from .page_routes import page_bp
from .user_routes import user_bp
from .auth_routes import auth_bp
from .renewal_routes import renewal_bp
from .notification_routes import notification_bp

def register_blueprints(app: Flask):
    """Register Flask blueprints."""
    app.register_blueprint(course_bp)
    app.register_blueprint(page_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(renewal_bp)
    app.register_blueprint(notification_bp)
