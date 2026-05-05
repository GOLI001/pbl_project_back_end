from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from models import User
import re

auth_bp = Blueprint('auth', __name__)
user_model = User()


def is_valid_email(email):
    """Валидация email"""
    pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    return re.match(pattern, email) is not None


@auth_bp.route('/register', methods=['POST'])
def register():
    """Регистрация нового пользователя"""
    data = request.get_json()

    email = data.get('email', '').strip()
    password = data.get('password', '')
    name = data.get('name', '').strip()

    # Валидация
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    if not is_valid_email(email):
        return jsonify({'error': 'Invalid email format'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    if not name:
        name = email.split('@')[0]

    # Создание пользователя
    user = user_model.create_user(email, password, name)

    if user:
        # Создаем токены
        access_token = create_access_token(identity=str(user['id']))
        refresh_token = create_refresh_token(identity=str(user['id']))

        return jsonify({
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
        }), 201
    else:
        return jsonify({'error': 'User with this email already exists'}), 409


@auth_bp.route('/login', methods=['POST'])
def login():
    """Вход пользователя"""
    data = request.get_json()

    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = user_model.authenticate(email, password)

    if user:
        access_token = create_access_token(identity=str(user['id']))
        refresh_token = create_refresh_token(identity=str(user['id']))

        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': user['id'],
                'email': user['email'],
                'name': user['name'],
                'level': user['level'],
                'streak': user['streak'],
                'screen_time_hours': user['screen_time_hours'],
                'screen_time_days': user['screen_time_days'],
                'achievements': user.get('achievements_list', [])
            },
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200
    else:
        return jsonify({'error': 'Invalid email or password'}), 401


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Обновление токена"""
    current_user_id = get_jwt_identity()
    access_token = create_access_token(identity=current_user_id)

    return jsonify({
        'access_token': access_token
    }), 200