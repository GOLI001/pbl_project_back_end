from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_restx import Api, Resource, fields, Namespace
from config import Config
from routes.auth import auth_bp
from routes.user import user_bp
from models import User
import os


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # CORS для Telegram Mini App
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
        description='API для приложения контроля экранного времени\n\n'
                    '**Telegram Mini App Backend**\n\n'
                    '## Использование:\n'
                    '1. Зарегистрируйтесь через /api/auth/register\n'
                    '2. Войдите через /api/auth/login\n'
                    '3. Используйте токен для доступа к API\n\n'
                    '## Авторизация:\n'
                    'Нажмите кнопку **Authorize** и введите токен в формате: `Bearer <token>`',
        doc='/api/docs',
        prefix='/api',
        authorizations={
            'Bearer': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'Authorization',
                'description': 'JWT токен в формате: Bearer eyJhbGciOiJIUzI1NiIs...'
            }
        },
        security='Bearer'
    )

    # ============ Модели для Swagger ============

    # Модель регистрации
    register_model = api.model('Register', {
        'email': fields.String(
            required=True,
            description='Email пользователя',
            example='user@example.com'
        ),
        'password': fields.String(
            required=True,
            description='Пароль (минимум 6 символов)',
            example='password123'
        ),
        'name': fields.String(
            description='Имя пользователя',
            example='John Doe'
        )
    })

    # Модель входа
    login_model = api.model('Login', {
        'email': fields.String(
            required=True,
            description='Email пользователя',
            example='user@example.com'
        ),
        'password': fields.String(
            required=True,
            description='Пароль',
            example='password123'
        )
    })

    # Модель ответа пользователя
    user_model_response = api.model('UserResponse', {
        'id': fields.Integer(description='ID пользователя'),
        'email': fields.String(description='Email'),
        'name': fields.String(description='Имя'),
        'level': fields.Integer(description='Уровень'),
        'streak': fields.Integer(description='Стрик дней'),
        'achievements': fields.List(fields.String, description='Достижения')
    })

    # Модель обновления стрика
    streak_model = api.model('StreakUpdate', {
        'streak': fields.Integer(
            required=True,
            description='Количество дней',
            example=7,
            min=0
        )
    })

    # Модель экранного времени
    screen_time_model = api.model('ScreenTimeSave', {
        'hours': fields.Float(
            required=True,
            description='Часы в день',
            example=2.5,
            min=0,
            max=24
        ),
        'days': fields.Integer(
            required=True,
            description='Дни в неделю',
            example=7,
            min=1,
            max=7
        )
    })

    # Модель ошибки
    error_model = api.model('Error', {
        'error': fields.String(description='Описание ошибки')
    })

    # ============ Auth Namespace ============
    auth_ns = api.namespace('auth', description='🔐 Аутентификация')

    @auth_ns.route('/register')
    class Register(Resource):
        @auth_ns.doc('register')
        @auth_ns.expect(register_model)
        @auth_ns.response(201, 'Пользователь создан')
        @auth_ns.response(400, 'Ошибка валидации', error_model)
        @auth_ns.response(409, 'Пользователь уже существует', error_model)
        def post(self):
            """📝 Регистрация нового пользователя"""
            data = request.get_json()

            email = data.get('email', '').strip()
            password = data.get('password', '')
            name = data.get('name', '').strip()

            if not email or not password:
                return {'error': 'Email and password are required'}, 400

            if len(password) < 6:
                return {'error': 'Password must be at least 6 characters'}, 400

            if not name:
                name = email.split('@')[0]

            user_model = User()
            user = user_model.create_user(email, password, name)

            if user:
                from flask_jwt_extended import create_access_token, create_refresh_token
                access_token = create_access_token(identity=str(user['id']))
                refresh_token = create_refresh_token(identity=str(user['id']))

                return {
                    'message': 'User created successfully',
                    'user': {
                        'id': user['id'],
                        'email': user['email'],
                        'name': user['name'],
                        'level': user['level'],
                        'streak': user['streak'],
                        'achievements': user.get('achievements_list', [])
                    },
                    'access_token': access_token,
                    'refresh_token': refresh_token
                }, 201
            else:
                return {'error': 'User with this email already exists'}, 409

    @auth_ns.route('/login')
    class Login(Resource):
        @auth_ns.doc('login')
        @auth_ns.expect(login_model)
        @auth_ns.response(200, 'Успешный вход')
        @auth_ns.response(401, 'Неверные учетные данные', error_model)
        def post(self):
            """🔑 Вход в систему"""
            data = request.get_json()

            email = data.get('email', '').strip()
            password = data.get('password', '')

            if not email or not password:
                return {'error': 'Email and password are required'}, 400

            user_model = User()
            user = user_model.authenticate(email, password)

            if user:
                from flask_jwt_extended import create_access_token, create_refresh_token
                access_token = create_access_token(identity=str(user['id']))
                refresh_token = create_refresh_token(identity=str(user['id']))

                return {
                    'message': 'Login successful',
                    'user': {
                        'id': user['id'],
                        'email': user['email'],
                        'name': user['name'],
                        'level': user['level'],
                        'streak': user['streak'],
                        'screen_time_hours': user.get('screen_time_hours', 0),
                        'screen_time_days': user.get('screen_time_days', 7),
                        'achievements': user.get('achievements_list', [])
                    },
                    'access_token': access_token,
                    'refresh_token': refresh_token
                }, 200
            else:
                return {'error': 'Invalid email or password'}, 401

    @auth_ns.route('/refresh')
    class Refresh(Resource):
        @auth_ns.doc('refresh', security='Bearer')
        @auth_ns.response(200, 'Токен обновлен')
        @auth_ns.response(401, 'Невалидный токен', error_model)
        def post(self):
            """🔄 Обновление access токена"""
            from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token

            @jwt_required(refresh=True)
            def refresh():
                current_user_id = get_jwt_identity()
                access_token = create_access_token(identity=current_user_id)
                return {'access_token': access_token}, 200

            return refresh()

    # ============ User Namespace ============
    user_ns = api.namespace('user', description='👤 Управление пользователем')

    @user_ns.route('/profile')
    class UserProfile(Resource):
        @user_ns.doc('get_profile', security='Bearer')
        @user_ns.response(200, 'Профиль пользователя', user_model_response)
        @user_ns.response(401, 'Не авторизован', error_model)
        @user_ns.response(404, 'Пользователь не найден', error_model)
        def get(self):
            """📋 Получение профиля пользователя"""
            from flask_jwt_extended import jwt_required, get_jwt_identity

            @jwt_required()
            def get_profile():
                user_id = int(get_jwt_identity())
                user_model = User()
                user = user_model.get_user_by_id(user_id)

                if user:
                    return {
                        'user': {
                            'id': user['id'],
                            'email': user['email'],
                            'name': user['name'],
                            'level': user['level'],
                            'streak': user['streak'],
                            'screen_time_hours': user.get('screen_time_hours', 0),
                            'screen_time_days': user.get('screen_time_days', 7),
                            'achievements': user.get('achievements_list', []),
                            'created_at': user['created_at']
                        }
                    }, 200
                else:
                    return {'error': 'User not found'}, 404

            return get_profile()

    @user_ns.route('/streak')
    class UserStreak(Resource):
        @user_ns.doc('update_streak', security='Bearer')
        @user_ns.expect(streak_model)
        @user_ns.response(200, 'Стрик обновлен')
        @user_ns.response(401, 'Не авторизован', error_model)
        def post(self):
            """🔥 Обновление стрика пользователя"""
            from flask_jwt_extended import jwt_required, get_jwt_identity

            @jwt_required()
            def update_streak():
                user_id = int(get_jwt_identity())
                data = request.get_json()
                streak = data.get('streak', 0)

                user_model = User()
                user = user_model.update_streak(user_id, streak)

                if user:
                    return {
                        'message': 'Streak updated',
                        'streak': user['streak'],
                        'achievements': user.get('achievements_list', [])
                    }, 200
                else:
                    return {'error': 'User not found'}, 404

            return update_streak()

    @user_ns.route('/screen-time')
    class ScreenTime(Resource):
        @user_ns.doc('save_screen_time', security='Bearer')
        @user_ns.expect(screen_time_model)
        @user_ns.response(200, 'Экранное время сохранено')
        @user_ns.response(401, 'Не авторизован', error_model)
        def post(self):
            """⏰ Сохранение экранного времени"""
            from flask_jwt_extended import jwt_required, get_jwt_identity

            @jwt_required()
            def save_screen_time():
                user_id = int(get_jwt_identity())
                data = request.get_json()

                hours = data.get('hours', 0)
                days = data.get('days', 7)

                user_model = User()
                user_model.save_screen_time(user_id, hours, days)
                user_model.update_user(user_id, {
                    'screen_time_hours': hours,
                    'screen_time_days': days
                })

                return {
                    'message': 'Screen time saved',
                    'screen_time': {
                        'hours': hours,
                        'days': days
                    }
                }, 200

            return save_screen_time()

        @user_ns.doc('get_screen_time_history', security='Bearer')
        @user_ns.response(200, 'История экранного времени')
        @user_ns.response(401, 'Не авторизован', error_model)
        def get(self):
            """📊 Получение истории экранного времени"""
            from flask_jwt_extended import jwt_required, get_jwt_identity

            @jwt_required()
            def get_history():
                user_id = int(get_jwt_identity())
                user_model = User()
                history = user_model.get_screen_time_history(user_id)
                return {'history': history}, 200

            return get_history()

    @user_ns.route('/achievements')
    class Achievements(Resource):
        @user_ns.doc('get_achievements', security='Bearer')
        @user_ns.response(200, 'Список достижений')
        @user_ns.response(401, 'Не авторизован', error_model)
        def get(self):
            """🏆 Получение достижений пользователя"""
            from flask_jwt_extended import jwt_required, get_jwt_identity

            @jwt_required()
            def get_achievements():
                user_id = int(get_jwt_identity())
                user_model = User()
                achievements = user_model.get_user_achievements(user_id)
                return {'achievements': achievements}, 200

            return get_achievements()

    @user_ns.route('/delete-account')
    class DeleteAccount(Resource):
        @user_ns.doc('delete_account', security='Bearer')
        @user_ns.response(200, 'Аккаунт удален')
        @user_ns.response(401, 'Не авторизован', error_model)
        def delete(self):
            """🗑️ Удаление аккаунта"""
            from flask_jwt_extended import jwt_required, get_jwt_identity

            @jwt_required()
            def delete_account():
                user_id = int(get_jwt_identity())
                user_model = User()

                conn = user_model.db.get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                conn.commit()
                conn.close()

                return {'message': 'Account deleted successfully'}, 200

            return delete_account()

    # Health check
    @app.route('/api/health')
    def health_check():
        """🏥 Проверка здоровья API"""
        return jsonify({
            'status': 'healthy',
            'message': 'Screen Time Awareness API is running',
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'docs': f"{request.url_root}api/docs"
        })

    # Главная страница
    @app.route('/')
    def index():
        return jsonify({
            'name': 'Screen Time Awareness API',
            'version': '1.0.0',
            'docs': f"{request.url_root}api/docs",
            'health': f"{request.url_root}api/health",
            'endpoints': {
                'auth': {
                    'register': 'POST /api/auth/register',
                    'login': 'POST /api/auth/login',
                    'refresh': 'POST /api/auth/refresh'
                },
                'user': {
                    'profile': 'GET /api/user/profile',
                    'streak': 'POST /api/user/streak',
                    'screen_time': 'POST /api/user/screen-time',
                    'screen_time_history': 'GET /api/user/screen-time/history',
                    'achievements': 'GET /api/user/achievements',
                    'delete_account': 'DELETE /api/user/delete-account'
                }
            }
        })

    return app


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app = create_app()
    print("=" * 60)
    print("🚀 Screen Time Awareness API")
    print("=" * 60)
    print(f"📚 Swagger UI: http://localhost:{port}/api/docs")
    print(f"🏥 Health Check: http://localhost:{port}/api/health")
    print(f"📡 API Base URL: http://localhost:{port}/api")
    print("=" * 60)
    app.run(debug=False, host='0.0.0.0', port=port)