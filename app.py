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

    # Swagger API
    api = Api(
        app,
        version='1.0.0',
        title='Screen Time Awareness API',
        description='API для приложения контроля экранного времени (Telegram Mini App)',
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

    # ---------- Модели для Swagger ----------
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
    points_model = api.model('Points', {
        'points': fields.Integer(required=True, example=100)
    })
    challenge_join_model = api.model('ChallengeJoin', {
        'challenge_id': fields.Integer(required=True, example=1)
    })
    challenge_progress_model = api.model('ChallengeProgress', {
        'challenge_id': fields.Integer(required=True, example=1),
        'progress': fields.Integer(required=True, example=5)
    })

    # ---------- Auth Namespace ----------
    auth_ns = api.namespace('auth', description='🔐 Аутентификация')

    @auth_ns.route('/register')
    class Register(Resource):
        @auth_ns.expect(register_model)
        @auth_ns.response(201, 'Пользователь создан')
        @auth_ns.response(400, 'Ошибка валидации')
        @auth_ns.response(409, 'Пользователь уже существует')
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
                    'user': {
                        'id': user['id'],
                        'email': user['email'],
                        'name': user['name'],
                        'level': user['level'],
                        'streak': user['streak'],
                        'points': user.get('points', 0)
                    },
                    'access_token': token
                }, 201
            return {'error': 'User exists'}, 409

    @auth_ns.route('/login')
    class Login(Resource):
        @auth_ns.expect(login_model)
        @auth_ns.response(200, 'Успешный вход')
        @auth_ns.response(401, 'Неверные учетные данные')
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
                    'user': {
                        'id': user['id'],
                        'email': user['email'],
                        'name': user['name'],
                        'level': user['level'],
                        'streak': user['streak'],
                        'points': user.get('points', 0)
                    },
                    'access_token': token
                }, 200
            return {'error': 'Invalid credentials'}, 401

    # ---------- User Namespace ----------
    user_ns = api.namespace('user', description='👤 Пользователь')

    @user_ns.route('/profile')
    class Profile(Resource):
        @user_ns.doc(security='Bearer')
        @user_ns.response(200, 'Профиль пользователя')
        @user_ns.response(401, 'Требуется авторизация')
        def get(self):
            """Получить профиль текущего пользователя"""
            from flask_jwt_extended import jwt_required, get_jwt_identity
            @jwt_required()
            def get_profile():
                user_id = int(get_jwt_identity())
                user = User().get_user_by_id(user_id)
                return jsonify({'user': user}) if user else (jsonify({'error': 'Not found'}), 404)
            return get_profile()

    @user_ns.route('/streak')
    class Streak(Resource):
        @user_ns.doc(security='Bearer')
        @user_ns.expect(streak_model)
        @user_ns.response(200, 'Стрик обновлен')
        def post(self):
            """Обновить стрик"""
            from flask_jwt_extended import jwt_required, get_jwt_identity
            @jwt_required()
            def update():
                user_id = int(get_jwt_identity())
                streak = request.get_json().get('streak', 0)
                user = User().update_streak(user_id, streak)
                return jsonify({'streak': user['streak']}) if user else (jsonify({'error': 'Not found'}), 404)
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
                hours = data.get('hours', 0)
                days = data.get('days', 7)
                user_model = User()
                user_model.save_screen_time(user_id, hours, days)
                user_model.update_user(user_id, {'screen_time_hours': hours, 'screen_time_days': days})
                return {'message': 'Saved'}, 200
            return save()

    @user_ns.route('/screen-time/history')
    class ScreenTimeHistory(Resource):
        @user_ns.doc(security='Bearer')
        def get(self):
            """История экранного времени (ручной ввод)"""
            from flask_jwt_extended import jwt_required, get_jwt_identity
            @jwt_required()
            def history():
                user_id = int(get_jwt_identity())
                history = User().get_screen_time_history(user_id)
                return jsonify({'history': history})
            return history()

    @user_ns.route('/achievements')
    class Achievements(Resource):
        @user_ns.doc(security='Bearer')
        def get(self):
            """Получить достижения"""
            from flask_jwt_extended import jwt_required, get_jwt_identity
            @jwt_required()
            def get_ach():
                user_id = int(get_jwt_identity())
                achievements = User().get_user_achievements(user_id)
                return jsonify({'achievements': achievements})
            return get_ach()

    @user_ns.route('/points')
    class Points(Resource):
        @user_ns.doc(security='Bearer')
        def get(self):
            """Получить текущее количество очков"""
            from flask_jwt_extended import jwt_required, get_jwt_identity
            @jwt_required()
            def get_pts():
                user_id = int(get_jwt_identity())
                pts = User().get_points(user_id)
                return {'points': pts}
            return get_pts()

        @user_ns.doc(security='Bearer')
        @user_ns.expect(points_model)
        def post(self):
            """Обновить очки (синхронизация с клиентом)"""
            from flask_jwt_extended import jwt_required, get_jwt_identity
            @jwt_required()
            def update_pts():
                user_id = int(get_jwt_identity())
                data = request.get_json()
                new_points = data.get('points', 0)
                user_model = User()
                current = user_model.get_points(user_id)
                delta = new_points - current
                if delta != 0:
                    user_model.update_points(user_id, delta, 'sync_from_client')
                return {'points': user_model.get_points(user_id)}
            return update_pts()

    @user_ns.route('/leaderboard')
    class Leaderboard(Resource):
        def get(self):
            """Таблица лидеров по очкам"""
            leaders = User().get_leaderboard()
            return jsonify({'leaders': leaders})

    @user_ns.route('/challenges')
    class Challenges(Resource):
        def get(self):
            """Активные челленджи"""
            challenges = User().get_active_challenges()
            return jsonify({'challenges': challenges})

    @user_ns.route('/challenges/join')
    class JoinChallenge(Resource):
        @user_ns.doc(security='Bearer')
        @user_ns.expect(challenge_join_model)
        def post(self):
            """Принять участие в челлендже"""
            from flask_jwt_extended import jwt_required, get_jwt_identity
            @jwt_required()
            def join():
                user_id = int(get_jwt_identity())
                challenge_id = request.get_json().get('challenge_id')
                if not challenge_id:
                    return {'error': 'challenge_id required'}, 400
                success = User().join_challenge(user_id, challenge_id)
                return {'message': 'Joined'} if success else ({'error': 'Already joined'}, 400)
            return join()

    @user_ns.route('/challenges/progress')
    class ChallengeProgress(Resource):
        @user_ns.doc(security='Bearer')
        @user_ns.expect(challenge_progress_model)
        def put(self):
            """Обновить прогресс в челлендже"""
            from flask_jwt_extended import jwt_required, get_jwt_identity
            @jwt_required()
            def update():
                user_id = int(get_jwt_identity())
                data = request.get_json()
                User().update_challenge_progress(user_id, data['challenge_id'], data['progress'])
                return {'message': 'Progress updated'}
            return update()

    @user_ns.route('/challenges/complete')
    class CompleteChallenge(Resource):
        @user_ns.doc(security='Bearer')
        @user_ns.expect(challenge_join_model)
        def post(self):
            """Завершить челлендж"""
            from flask_jwt_extended import jwt_required, get_jwt_identity
            @jwt_required()
            def complete():
                user_id = int(get_jwt_identity())
                challenge_id = request.get_json().get('challenge_id')
                User().complete_challenge(user_id, challenge_id)
                return {'message': 'Challenge completed'}
            return complete()

    # ---------- Report Namespace (скриншоты) ----------
    report_ns = api.namespace('report', description='📊 Отчёты и OCR')

    @report_ns.route('/screen-time')
    class ReportScreenTime(Resource):
        @report_ns.doc(security='Bearer')
        def post(self):
            """Загрузить скриншот экранного времени (OCR)"""
            from flask_jwt_extended import jwt_required, get_jwt_identity
            @jwt_required()
            def report():
                from routes.report import report_screen_time
                return report_screen_time()
            return report()

    @report_ns.route('/screen-time/history')
    class ReportHistory(Resource):
        @report_ns.doc(security='Bearer')
        def get(self):
            """История отчётов со скриншотами"""
            from flask_jwt_extended import jwt_required, get_jwt_identity
            @jwt_required()
            def history():
                user_id = int(get_jwt_identity())
                logs = User().get_screen_time_logs(user_id)
                return jsonify({'logs': logs})
            return history()

    @report_ns.route('/leaderboard')
    class ReportLeaderboard(Resource):
        def get(self):
            """Дублирующий маршрут лидерборда (для совместимости)"""
            leaders = User().get_leaderboard()
            return jsonify({'leaders': leaders})

    # ---------- Отладочный маршрут (временно) ----------
    @app.route('/api/debug/users')
    def debug_users():
        import sqlite3
        conn = sqlite3.connect(Config.DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, email, points, streak FROM users')
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(users)

    # ---------- Health Check ----------
    @app.route('/api/health')
    def health():
        return {'status': 'ok'}, 200

    # ---------- Убираем регистрацию старых Blueprint'ов, чтобы не было конфликтов ----------
    # (auth_bp, user_bp, report_bp больше не регистрируются)

    return app

# Глобальная переменная для gunicorn
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)