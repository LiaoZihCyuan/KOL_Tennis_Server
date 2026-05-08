import pkgutil
import importlib
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate



# Initialize extensions but without app context
db = SQLAlchemy()
migrate = Migrate()


def register_shell_context(app):
    """
    Registers a shell context processor that dynamically adds all
    non-abstract model classes to the shell context, and ensures all model
    modules are imported for Alembic to detect changes.
    """
    import models  # Import the models package
    from models.base import BaseModel

    model_classes = {}
    # Iterate over all modules in the 'models' package to import them
    for module_info in pkgutil.iter_modules(models.__path__, models.__name__ + '.'):
        module = importlib.import_module(module_info.name)
        # Find all classes in the module that are subclasses of BaseModel
        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)
            if isinstance(attribute, type) and \
               issubclass(attribute, BaseModel) and \
               attribute is not BaseModel and \
               not getattr(attribute, '__abstract__', False):
                model_classes[attribute.__name__] = attribute

    @app.shell_context_processor
    def make_shell_context():
        """
        Automatically adds all non-abstract model classes to the shell context.
        """
        return {
            'db': db,
            **model_classes
        }
