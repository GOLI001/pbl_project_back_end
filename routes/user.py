# routes/user.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User

user_bp = Blueprint('user', __name__)
user_model = User()

@user_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    user_id = int(get_jwt_identity())
    user = user_model.get_user_by_id(user_id)
    if user:
        return jsonify({'user': user}), 200
    return jsonify({'error': 'User not found'}), 404

@user_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    user = user_model.update_user(user_id, data)
    if user:
        return jsonify({'message': 'Profile updated', 'user': user}), 200
    return jsonify({'error': 'User not found'}), 404

@user_bp.route('/streak', methods=['POST'])
@jwt_required()
def update_streak():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    streak = data.get('streak', 0)
    user = user_model.update_streak(user_id, streak)
    if user:
        return jsonify({'message': 'Streak updated', 'streak': user['streak'], 'achievements': user.get('achievements_list', [])}), 200
    return jsonify({'error': 'User not found'}), 404

@user_bp.route('/screen-time', methods=['POST'])
@jwt_required()
def save_screen_time():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    hours = data.get('hours', 0)
    days = data.get('days', 7)
    user_model.save_screen_time(user_id, hours, days)
    user_model.update_user(user_id, {
        'screen_time_hours': hours,
        'screen_time_days': days
    })
    return jsonify({'message': 'Screen time saved'}), 200

@user_bp.route('/screen-time/history', methods=['GET'])
@jwt_required()
def get_screen_time_history():
    user_id = int(get_jwt_identity())
    history = user_model.get_screen_time_history(user_id)
    return jsonify({'history': history}), 200

@user_bp.route('/achievements', methods=['GET'])
@jwt_required()
def get_achievements():
    user_id = int(get_jwt_identity())
    achievements = user_model.get_user_achievements(user_id)
    return jsonify({'achievements': achievements}), 200

@user_bp.route('/points', methods=['GET'])
@jwt_required()
def get_points():
    user_id = int(get_jwt_identity())
    points = user_model.get_points(user_id)
    return jsonify({'points': points}), 200

@user_bp.route('/points', methods=['POST'])
@jwt_required()
def update_points():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    points = data.get('points', 0)
    user_model.update_points(user_id, points)  # здесь points — абсолютное значение? В модели мы делаем delta.
    # В старой версии update_points принимала delta, а здесь передаётся абсолютное значение. Нужно поправить.
    # Проще оставить как есть, но в models.py мы изменим update_points, чтобы он принимал delta.
    # Сейчас в models.py update_points принимает points_delta, поэтому перед вызовом надо вычислить разницу.
    # Чтобы не усложнять, пусть этот эндпоинт принимает абсолютные очки, а мы внутри обновим.
    current_points = user_model.get_points(user_id)
    delta = points - current_points
    user_model.update_points(user_id, delta)
    return jsonify({'message': 'Points updated', 'points': points}), 200

@user_bp.route('/challenges', methods=['GET'])
def get_challenges():
    challenges = user_model.get_active_challenges()
    return jsonify({'challenges': challenges}), 200

@user_bp.route('/challenges/join', methods=['POST'])
@jwt_required()
def join_challenge():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    challenge_id = data.get('challenge_id')
    if not challenge_id:
        return jsonify({'error': 'challenge_id required'}), 400
    success = user_model.join_challenge(user_id, challenge_id)
    if success:
        return jsonify({'message': 'Joined challenge'}), 200
    return jsonify({'error': 'Already joined or invalid'}), 400

@user_bp.route('/challenges/progress', methods=['PUT'])
@jwt_required()
def update_challenge_progress():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    challenge_id = data.get('challenge_id')
    progress = data.get('progress', 0)
    if not challenge_id:
        return jsonify({'error': 'challenge_id required'}), 400
    user_model.update_challenge_progress(user_id, challenge_id, progress)
    return jsonify({'message': 'Progress updated'}), 200

@user_bp.route('/challenges/complete', methods=['POST'])
@jwt_required()
def complete_challenge():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    challenge_id = data.get('challenge_id')
    if not challenge_id:
        return jsonify({'error': 'challenge_id required'}), 400
    user_model.complete_challenge(user_id, challenge_id)
    return jsonify({'message': 'Challenge completed'}), 200

@user_bp.route('/leaderboard', methods=['GET'])
def leaderboard():
    leaders = user_model.get_leaderboard()
    return jsonify({'leaders': leaders}), 200