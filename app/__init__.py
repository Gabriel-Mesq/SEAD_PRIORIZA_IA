from flask import Flask
from flask_session import Session
import os
def create_app():
    app = Flask(__name__)
    app.template_folder = 'templates'
    app.secret_key = os.urandom(24)    
    app.config['SESSION_TYPE'] = 'filesystem'
    Session(app)
    return app
