import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv
from datetime import datetime   # keep this
# remove the next line if present: import datetime
from flask import current_app
load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object('app.config.Config')
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    @app.context_processor
    def inject_current_year():
        return {'current_year': datetime.utcnow().year}

    with app.app_context():
        from . import routes, models
        db.create_all()
    return app
