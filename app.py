from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity, create_access_token
from flask_restx import Api, Resource, fields
from config import Config
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
        description='API для Telegram Mini App',
        doc='/api/docs',
        prefix='/api',
        authorizations={
            'Bearer': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'Authorization',
                'description': 'JWT: Bearer <token>'
            }
        },
        security='Bearer'
    )

    # ---------- Модели ----------
    register_model = api.model('Register', {
        'email': fields.String(required=True, example='user@example.com'),
        'password': fields.String(required=True, example='password123'),
        'name': fields.String(example='John')
    })
    login_model = api.model('Login', {
        'email': fields.String(required=True, example='user@example.com'),
        'password': fields.String(required=True, example='password123')
    })
    streak_model = api.model('Streak', {'streak': fields.Integer(required=True, example=7)})
    screen_time_model = api.model('ScreenTime', {
        'hours': fields.Float(required=True, example=2.5),
        'days': fields.Integer(required=True, example=7)
    })
    points_model = api.model('Points', {'points': fields.Integer(required=True, example=100)})
    challenge_join = api.model('ChallengeJoin', {'challenge_id': fields.Integer(required=True, example=1)})
    challenge_progress = api.model('ChallengeProgress', {
        'challenge_id': fields.Integer(required=True, example=1),
        'progress': fields.Integer(required=True, example=5)
    })

    # ---------- Auth Namespace ----------
    auth_ns = api.namespace('auth', description='Auth')
    @auth_ns.route('/register')
    class Register(Resource):
        @auth_ns.expect(register_model)
        def post(self):
            data = request.get_json()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            name = data.get('name', '').strip() or email.split('@')[0]
            if not email or not password:
                return {'error': 'Email and password required'}, 400
            if len(password) < 6:
                return {'error': 'Password min 6 characters'}, 400
            user = User().create_user(email, password, name)
            if user:
                token = create_access_token(identity=str(user['id']))
                return {
                    'message': 'Created',
                    'user': {'id': user['id'], 'email': user['email'], 'name': user['name'], 'level': user['level'], 'streak': user['streak'], 'points': user.get('points', 0)},
                    'access_token': token
                }, 201
            return {'error': 'User exists'}, 409

    @auth_ns.route('/login')
    class Login(Resource):
        @auth_ns.expect(login_model)
        def post(self):
            data = request.get_json()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            if not email or not password:
                return {'error': 'Email and password required'}, 400
            user = User().authenticate(email, password)
            if user:
                token = create_access_token(identity=str(user['id']))
                return {
                    'message': 'Success',
                    'user': {'id': user['id'], 'email': user['email'], 'name': user['name'], 'level': user['level'], 'streak': user['streak'], 'points': user.get('points', 0)},
                    'access_token': token
                }, 200
            return {'error': 'Invalid credentials'}, 401

    # ---------- User Namespace ----------
    user_ns = api.namespace('user', description='User')

    @user_ns.route('/profile')
    class Profile(Resource):
        @jwt_required()
        def get(self):
            user = User().get_user_by_id(int(get_jwt_identity()))
            if user:
                return {'user': user}, 200
            return {'error': 'Not found'}, 404

    @user_ns.route('/streak')
    class Streak(Resource):
        @jwt_required()
        @user_ns.expect(streak_model)
        def post(self):
            user = User().update_streak(int(get_jwt_identity()), request.get_json().get('streak', 0))
            if user:
                return {'streak': user['streak']}, 200
            return {'error': 'Not found'}, 404

    @user_ns.route('/screen-time')
    class ScreenTime(Resource):
        @jwt_required()
        @user_ns.expect(screen_time_model)
        def post(self):
            data = request.get_json()
            user_id = int(get_jwt_identity())
            u = User()
            u.save_screen_time(user_id, data.get('hours', 0), data.get('days', 7))
            u.update_user(user_id, {'screen_time_hours': data['hours'], 'screen_time_days': data['days']})
            return {'message': 'Saved'}, 200

    @user_ns.route('/screen-time/history')
    class ScreenTimeHistory(Resource):
        @jwt_required()
        def get(self):
            history = User().get_screen_time_history(int(get_jwt_identity()))
            return {'history': history}, 200

    @user_ns.route('/achievements')
    class Achievements(Resource):
        @jwt_required()
        def get(self):
            achievements = User().get_user_achievements(int(get_jwt_identity()))
            return {'achievements': achievements}, 200

    @user_ns.route('/points')
    class Points(Resource):
        @jwt_required()
        def get(self):
            pts = User().get_points(int(get_jwt_identity()))
            return {'points': pts}, 200

        @jwt_required()
        @user_ns.expect(points_model)
        def post(self):
            user_id = int(get_jwt_identity())
            new_points = request.get_json().get('points', 0)
            u = User()
            cur = u.get_points(user_id)
            delta = new_points - cur
            if delta != 0:
                u.update_points(user_id, delta, 'sync_from_client')
            return {'points': u.get_points(user_id)}, 200

    @user_ns.route('/leaderboard')
    class Leaderboard(Resource):
        def get(self):
            return {'leaders': User().get_leaderboard()}, 200

    @user_ns.route('/challenges')
    class Challenges(Resource):
        def get(self):
            return {'challenges': User().get_active_challenges()}, 200

    @user_ns.route('/challenges/join')
    class JoinChallenge(Resource):
        @jwt_required()
        @user_ns.expect(challenge_join)
        def post(self):
            ok = User().join_challenge(int(get_jwt_identity()), request.get_json().get('challenge_id'))
            if ok:
                return {'message': 'Joined'}, 200
            return {'error': 'Already joined'}, 400

    @user_ns.route('/challenges/progress')
    class ChallengeProgress(Resource):
        @jwt_required()
        @user_ns.expect(challenge_progress)
        def put(self):
            d = request.get_json()
            User().update_challenge_progress(int(get_jwt_identity()), d['challenge_id'], d['progress'])
            return {'message': 'Progress updated'}, 200

    @user_ns.route('/challenges/complete')
    class CompleteChallenge(Resource):
        @jwt_required()
        @user_ns.expect(challenge_join)
        def post(self):
            User().complete_challenge(int(get_jwt_identity()), request.get_json().get('challenge_id'))
            return {'message': 'Completed'}, 200

    # ---------- Report Namespace (OCR) ----------
    report_ns = api.namespace('report', description='Reports')
    @report_ns.route('/screen-time')
    class ReportScreenTime(Resource):
        @jwt_required()
        def post(self):
            from routes.report import report_screen_time
            return report_screen_time()

    @report_ns.route('/screen-time/history')
    class ReportHistory(Resource):
        @jwt_required()
        def get(self):
            logs = User().get_screen_time_logs(int(get_jwt_identity()))
            return {'logs': logs}, 200

    @report_ns.route('/leaderboard')
    class ReportLeaderboard(Resource):
        def get(self):
            return {'leaders': User().get_leaderboard()}, 200

    # ---------- Health ----------
    @app.route('/api/health')
    def health():
        return {'status': 'ok'}, 200

    return app

# Глобальная переменная для gunicorn
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)