# routes/report.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User, Database
from utils.ocr import extract_screen_time
import os
from datetime import date
from werkzeug.utils import secure_filename

report_bp = Blueprint('report', __name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@report_bp.route('/screen-time', methods=['POST'])
@jwt_required()
def report_screen_time():
    user_id = int(get_jwt_identity())
    if 'screenshot' not in request.files:
        return jsonify({'error': 'No screenshot provided'}), 400

    file = request.files['screenshot']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    filename = secure_filename(f"{user_id}_{date.today()}.png")
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    # OCR
    with open(filepath, 'rb') as f:
        img_bytes = f.read()
    minutes = extract_screen_time(img_bytes)

    user_model = User()
    log_id = user_model.save_screen_time_log(user_id, filepath, minutes, date.today())

    # Начисление очков за верификацию
    if minutes > 0:
        # Цель: сравнить с предыдущим днём (упрощённо: за загрузку скриншота даём 10 очков + бонус за снижение)
        previous_logs = user_model.get_screen_time_logs(user_id)
        bonus = 0
        if len(previous_logs) > 1:
            yesterday = previous_logs[1]['recognized_minutes']  # предыдущий день
            if minutes < yesterday:
                bonus = 15  # бонус за снижение
        user_model.update_points(user_id, 10 + bonus, f'Отчёт экранного времени за {date.today()}')
    else:
        return jsonify({'error': 'Could not recognize screen time. Please try with a clearer screenshot.'}), 422

    return jsonify({
        'message': 'Screen time reported',
        'recognized_minutes': minutes,
        'log_id': log_id
    }), 201

@report_bp.route('/screen-time/history', methods=['GET'])
@jwt_required()
def get_screen_time_history():
    user_id = int(get_jwt_identity())
    user_model = User()
    logs = user_model.get_screen_time_logs(user_id)
    return jsonify({'logs': logs}), 200

@report_bp.route('/leaderboard', methods=['GET'])
def leaderboard():
    user_model = User()
    leaders = user_model.get_leaderboard()
    return jsonify({'leaders': leaders}), 200