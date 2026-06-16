from django.apps import AppConfig
from django.db.utils import OperationalError, ProgrammingError


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Initialize DB extensions and vector column/indexes if possible
        try:
            from .dbinit import run_db_init
            run_db_init()
        except (OperationalError, ProgrammingError):
            # DB might not be ready during migrations; ignore
            pass
        except Exception:
            # Keep startup resilient; detailed logs will be handled by logging config
            pass
