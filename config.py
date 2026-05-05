import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
    DATABASE = os.environ.get('DATABASE_URL', 'users.db')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)

    # CORS - добавьте ваш домен Vercel
    CORS_ORIGINS = [
        'https://digital-trap-git-main-goliahmadi77-5666s-projects.vercel.app',
        'https://digital-trap.vercel.app',
        'http://localhost:5500',
        'http://localhost:3000'
    ]