import sqlite3
import hashlib
import secrets
from datetime import datetime
from config import Config


class Database:
    def __init__(self):
        self.db_path = Config.DATABASE
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                streak INTEGER DEFAULT 0,
                achievements TEXT DEFAULT '[]',
                screen_time_hours REAL DEFAULT 0,
                screen_time_days INTEGER DEFAULT 7,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица сессий/токенов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                token_type TEXT DEFAULT 'access',
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        # Таблица достижений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                achievement_name TEXT NOT NULL,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE(user_id, achievement_name)
            )
        ''')

        # Таблица истории экранного времени
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS screen_time_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                hours REAL NOT NULL,
                days INTEGER NOT NULL,
                recorded_at DATE DEFAULT CURRENT_DATE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        conn.close()


class User:
    def __init__(self):
        self.db = Database()

    @staticmethod
    def hash_password(password):
        """Хеширование пароля"""
        salt = secrets.token_hex(16)
        return hashlib.sha256(f"{password}{salt}".encode()).hexdigest() + f":{salt}"

    @staticmethod
    def verify_password(password, password_hash):
        """Проверка пароля"""
        try:
            hash_part, salt = password_hash.split(':')
            return hash_part == hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
        except:
            return False

    def create_user(self, email, password, name):
        """Создание нового пользователя"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            password_hash = self.hash_password(password)
            cursor.execute(
                'INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)',
                (email.lower(), password_hash, name)
            )
            conn.commit()
            user_id = cursor.lastrowid

            # Добавляем первое достижение
            cursor.execute(
                'INSERT INTO achievements (user_id, achievement_name) VALUES (?, ?)',
                (user_id, 'First Day')
            )
            conn.commit()

            return self.get_user_by_id(user_id)
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def get_user_by_email(self, email):
        """Получение пользователя по email"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE email = ?', (email.lower(),))
        user = cursor.fetchone()
        conn.close()

        return dict(user) if user else None

    def get_user_by_id(self, user_id):
        """Получение пользователя по ID"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()

        if user:
            user_dict = dict(user)
            # Получаем достижения
            achievements = self.get_user_achievements(user_id)
            user_dict['achievements_list'] = achievements
            return user_dict
        return None

    def authenticate(self, email, password):
        """Аутентификация пользователя"""
        user = self.get_user_by_email(email)
        if user and self.verify_password(password, user['password_hash']):
            return user
        return None

    def update_user(self, user_id, data):
        """Обновление данных пользователя"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        allowed_fields = ['name', 'level', 'streak', 'screen_time_hours', 'screen_time_days']
        updates = []
        values = []

        for field in allowed_fields:
            if field in data:
                updates.append(f'{field} = ?')
                values.append(data[field])

        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            values.append(user_id)
            cursor.execute(
                f'UPDATE users SET {", ".join(updates)} WHERE id = ?',
                values
            )
            conn.commit()

        conn.close()
        return self.get_user_by_id(user_id)

    def update_streak(self, user_id, streak):
        """Обновление стрика"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            'UPDATE users SET streak = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (streak, user_id)
        )
        conn.commit()

        # Проверяем достижения
        if streak >= 7:
            self.add_achievement(user_id, 'Week Hero')
        if streak >= 30:
            self.add_achievement(user_id, '30 Days')
        if streak >= 100:
            self.add_achievement(user_id, 'Master')

        conn.close()
        return self.get_user_by_id(user_id)

    def add_achievement(self, user_id, achievement_name):
        """Добавление достижения"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                'INSERT INTO achievements (user_id, achievement_name) VALUES (?, ?)',
                (user_id, achievement_name)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_user_achievements(self, user_id):
        """Получение достижений пользователя"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            'SELECT achievement_name, unlocked_at FROM achievements WHERE user_id = ? ORDER BY unlocked_at DESC',
            (user_id,)
        )
        achievements = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return achievements

    def save_screen_time(self, user_id, hours, days):
        """Сохранение истории экранного времени"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            'INSERT INTO screen_time_history (user_id, hours, days) VALUES (?, ?, ?)',
            (user_id, hours, days)
        )
        conn.commit()
        conn.close()

    def get_screen_time_history(self, user_id, limit=30):
        """Получение истории экранного времени"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            'SELECT * FROM screen_time_history WHERE user_id = ? ORDER BY recorded_at DESC LIMIT ?',
            (user_id, limit)
        )
        history = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return history