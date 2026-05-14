import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or "change-me"
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or "sqlite:///dev.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
