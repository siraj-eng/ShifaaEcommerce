from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Single shared instances for the whole app
db = SQLAlchemy()
login_manager = LoginManager()






