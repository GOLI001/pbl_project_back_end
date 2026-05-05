# app.py
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_restx import Api, Resource, fields
from config import Config
from routes.auth import auth_bp
from routes.user import user_bp
from routes.report import report_bp
from models import User
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # CORS
    CORS(app,
         origins=Config.CORS_ORIGINS,
         supports_credentials=True,
         allow_headers=['Content-Type', 'Authorization'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])

    # JWT
    jwt = JWTManager(app)

    # Swagger
    api = Api(
        app,
        version='1.0.0',
        title='Screen Time Awareness API',
        description='API для контроля экранного времени с верификацией через скриншоты',
        doc='/api/docs',
        prefix='/api',
        authorizations={
            'Bearer': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'Authorization',
                'description': 'JWT токен в формате: Bearer <token>'
            }
        },
        security='Bearer'
    )

    # Модели для Swagger
    register_model = api.model('Register', {
        'email': fields.String(required=True, example='user@example.com'),
        'password': fields.String(required=True, example='password123'),
        'name': fields.String(example='John Doe')
    })
    login_model = api.model('Login', {
        'email': fields.String(required=True, example='user@example.com'),
        'password': fields.String(required=True, example='password123')
    })
    streak_model = api.model('Streak', {
        'streak': fields.Integer(required=True, example=7)
    })
    screen_time_model = api.model('ScreenTime', {
        'hours': fields.Float(required=True, example=2.5),
        'days': fields.Integer(required=True, example=7)
    })

    # Auth namespace
    auth_ns = api.namespace('auth', description='Аутентификация')
    @auth_ns.route('/register')
    class Register(Resource):
        @auth_ns.expect(register_model)
        def post(self):
            """Регистрация нового пользователя"""
            data = request.get_json()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            name = data.get('name', '').strip() or email.split('@')[0]

            if not email or not password:
                return {'error': 'Email and password required'}, 400
            if len(password) < 6:
                return {'error': 'Password min 6 characters'}, 400

            user_model = User()
            user = user_model.create_user(email, password, name)
            if user:
                from flask_jwt_extended import create_access_token
                token = create_access_token(identity=str(user['id']))
                return {
                    'message': 'Created',
                    'user': {'id': user['id'], 'email': user['email'], 'name': user['name'], 'level': user['level'], 'streak': user['streak']},
                    'access_token': token
                }, 201
            return {'error': 'User exists'}, 409

    @auth_ns.route('/login')
    class Login(Resource):
        @auth_ns.expect(login_model)
        def post(self):
            """Вход пользователя"""
            data = request.get_json()
            email = data.get('email', '').strip()
            password = data.get('password', '')

            if not email or not password:
                return {'error': 'Email and password required'}, 400

            user_model = User()
            user = user_model.authenticate(email, password)
            if user:
                from flask_jwt_extended import create_access_token
                token = create_access_token(identity=str(user['id']))
                return {
                    'message': 'Success',
                    'user': {'id': user['id'], 'email': user['email'], 'name': user['name'], 'level': user['level'], 'streak': user['streak']},
                    'access_token': token
                }, 200
            return {'error': 'Invalid credentials'}, 401

    # User namespace
    user_ns = api.namespace('user', description='Управление пользователем')
    @user_ns.route('/profile')
    class Profile(Resource):
        @user_ns.doc(security='Bearer')
        def get(self):
            """Получить профиль"""
            from flask_jwt_extended import jwt_required, get_jwt_identity
            @jwt_required()
            def get_profile():
                user_id = int(get_jwt_identity())
                user_model = User()
                user = user_model.get_user_by_id(user_id)
                if user:
                    return {'user': user}, 200
                return {'error': 'Not found'}, 404
            return get_profile()

    @user_ns.route('/streak')
    class Streak(Resource):
        @user_ns.doc(security='Bearer')
        @user_ns.expect(streak_model)
        def post(self):
            """Обновить стрик"""
            from flask_jwt_extended import jwt_required, get_jwt_identity
            @jwt_required()
            def update():
                user_id = int(get_jwt_identity())
                streak = request.get_json().get('streak', 0)
                user_model = User()
                user = user_model.update_streak(user_id, streak)
                return {'streak': user['streak']} if user else ({'error': 'Not found'}, 404)
            return update()

    @user_ns.route('/screen-time')
    class ScreenTime(Resource):
        @user_ns.doc(security='Bearer')
        @user_ns.expect(screen_time_model)
        def post(self):
            """Сохранить экранное время (ручной ввод)"""
            from flask_jwt_extended import jwt_required, get_jwt_identity
            @jwt_required()
            def save():
                user_id = int(get_jwt_identity())
                data = request.get_json()
                user_model = User()
                user_model.save_screen_time(user_id, data.get('hours', 0), data.get('days', 7))
                return {'message': 'Saved'}, 200
            return save()

    # Регистрация blueprints (дополнительные маршруты)
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(user_bp, url_prefix='/api/user')
    app.register_blueprint(report_bp, url_prefix='/api/report')

    @app.route('/api/debug/users')
    def debug_users():
        import sqlite3
        conn = sqlite3.connect('users.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, email, points, streak FROM users')
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(users)

    # Health check
    @app.route('/api/health')
    def health():
        return {'status': 'ok'}, 200

    return app

# 🔥 ВАЖНО: глобальная переменная app для gunicorn
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)