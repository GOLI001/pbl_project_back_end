from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User

user_bp = Blueprint('user', __name__)
user_model = User()


@user_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Получение профиля пользователя"""
    user_id = int(get_jwt_identity())
    user = user_model.get_user_by_id(user_id)

    if user:
        return jsonify({
            'user': {
                'id': user['id'],
                'email': user['email'],
                'name': user['name'],
                'level': user['level'],
                'streak': user['streak'],
                'screen_time_hours': user['screen_time_hours'],
                'screen_time_days': user['screen_time_days'],
                'achievements': user.get('achievements_list', []),
                'created_at': user['created_at']
            }
        }), 200
    else:
        return jsonify({'error': 'User not found'}), 404


@user_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Обновление профиля"""
    user_id = int(get_jwt_identity())
    data = request.get_json()

    user = user_model.update_user(user_id, data)

    if user:
        return jsonify({
            'message': 'Profile updated',
            'user': {
                'id': user['id'],
                'email': user['email'],
                'name': user['name'],
                'level': user['level'],
                'streak': user['streak']
            }
        }), 200
    else:
        return jsonify({'error': 'User not found'}), 404


@user_bp.route('/streak', methods=['POST'])
@jwt_required()
def update_streak():
    """Обновление стрика"""
    user_id = int(get_jwt_identity())
    data = request.get_json()

    streak = data.get('streak', 0)
    user = user_model.update_streak(user_id, streak)

    if user:
        return jsonify({
            'message': 'Streak updated',
            'streak': user['streak'],
            'achievements': user.get('achievements_list', [])
        }), 200
    else:
        return jsonify({'error': 'User not found'}), 404


@user_bp.route('/screen-time', methods=['POST'])
@jwt_required()
def save_screen_time():
    """Сохранение экранного времени"""
    user_id = int(get_jwt_identity())
    data = request.get_json()

    hours = data.get('hours', 0)
    days = data.get('days', 7)

    # Сохраняем в историю
    user_model.save_screen_time(user_id, hours, days)

    # Обновляем текущие значения
    user_model.update_user(user_id, {
        'screen_time_hours': hours,
        'screen_time_days': days
    })

    return jsonify({
        'message': 'Screen time saved'
    }), 200


@user_bp.route('/screen-time/history', methods=['GET'])
@jwt_required()
def get_screen_time_history():
    """Получение истории экранного времени"""
    user_id = int(get_jwt_identity())
    history = user_model.get_screen_time_history(user_id)

    return jsonify({
        'history': history
    }), 200


@user_bp.route('/achievements', methods=['GET'])
@jwt_required()
def get_achievements():
    """Получение достижений"""
    user_id = int(get_jwt_identity())
    achievements = user_model.get_user_achievements(user_id)

    return jsonify({
        'achievements': achievements
    }), 200


@user_bp.route('/delete-account', methods=['DELETE'])
@jwt_required()
def delete_account():
    """Удаление аккаунта"""
    user_id = int(get_jwt_identity())

    conn = user_model.db.get_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

    return jsonify({
        'message': 'Account deleted successfully'
    }), 200