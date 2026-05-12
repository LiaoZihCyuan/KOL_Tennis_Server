from flask import Flask
from .course_routes import course_bp
from .page_routes import page_bp
from .user_routes import user_bp

def register_blueprints(app: Flask):
    """Register Flask blueprints."""
    app.register_blueprint(course_bp)
    app.register_blueprint(page_bp)
    app.register_blueprint(user_bp)
