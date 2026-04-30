import os
from flask import Flask
from flask_migrate import Migrate
from extensions import db

# Import all models for Alembic to detect them
# These imports are crucial for Flask-Migrate to discover your models.
# As new models are created in the 'models' directory, they should be imported here.
# Also import the base model for declarative base to be registered.
import models.user
import models.course_template
import models.credit_wallet
import models.court
import models.schedule
import models.booking


from models.base import Base # Import Base for Alembic to detect models
def create_app():
    app = Flask(__name__)

    # Configuration
    # Use environment variable for DATABASE_URL, falling back to a default for local development
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://appuser:apppass@localhost:5432/appdb"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  # Recommended for Flask-SQLAlchemy 2.x
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "a_very_secret_key_for_dev") # Placeholder for a secret key

    # Initialize extensions
    db.init_app(app)
    Migrate(app, db)  # Initialize Flask-Migrate with the app and db

    # Register blueprints (example placeholder)
    # from .api import api_bp
    # app.register_blueprint(api_bp, url_prefix='/api')

    return app

# Create the Flask application instance, which Gunicorn will use
app = create_app()