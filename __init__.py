import os
from flask import Flask
from extensions import db, migrate, register_shell_context
from routes import register_blueprints

def create_app(config_name='development'):
    app = Flask(__name__)

    # Configuration
    # Use environment variable for DATABASE_URL and SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://appuser:apppass@localhost:5432/appdb"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  # Recommended for Flask-SQLAlchemy 2.x
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "a_very_secret_key_for_dev")

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)  # Initialize Flask-Migrate with the app and db

    # Register blueprints
    register_blueprints(app)

    # Register shell context
    register_shell_context(app)

    return app
