import os

from application.factory import create_app

# Default to the production config: DevelopmentConfig turns authentication off,
# so it must be asked for explicitly (.flaskenv and docker-compose.yml do).
app = create_app(os.getenv("FLASK_CONFIG") or "application.config.Config")
