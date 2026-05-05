from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

def admin_required():
    """Декоратор для админ-доступа"""
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            # Здесь можно добавить проверку на админа
            return fn(*args, **kwargs)
        return decorator
    return wrapper