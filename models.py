# models.py
import sqlite3
import hashlib
import secrets
from datetime import datetime, date
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

        # Пользователи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                streak INTEGER DEFAULT 0,
                points INTEGER DEFAULT 0,
                achievements TEXT DEFAULT '[]',
                screen_time_hours REAL DEFAULT 0,
                screen_time_days INTEGER DEFAULT 7,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Достижения
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

        # История ручного ввода экранного времени (кнопка Calculate)
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

        # Логи загруженных скриншотов и распознанного времени
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS screen_time_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                image_path TEXT,
                recognized_minutes INTEGER,
                reported_date DATE NOT NULL,
                verified BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        # Челленджи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                goal_type TEXT NOT NULL,
                goal_value INTEGER,
                reward_points INTEGER DEFAULT 50,
                duration_days INTEGER DEFAULT 7,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Участие в челленджах
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                challenge_id INTEGER NOT NULL,
                progress INTEGER DEFAULT 0,
                completed BOOLEAN DEFAULT 0,
                started_at DATE DEFAULT CURRENT_DATE,
                completed_at DATE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (challenge_id) REFERENCES challenges (id)
            )
        ''')

        # Лог начисления очков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS points_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        conn.commit()
        conn.close()


class User:
    def __init__(self):
        self.db = Database()

    @staticmethod
    def hash_password(password):
        salt = secrets.token_hex(16)
        return hashlib.sha256(f"{password}{salt}".encode()).hexdigest() + f":{salt}"

    @staticmethod
    def verify_password(password, password_hash):
        try:
            hash_part, salt = password_hash.split(':')
            return hash_part == hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
        except:
            return False

    def create_user(self, email, password, name):
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
            # Первое достижение
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
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email.lower(),))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None

    def get_user_by_id(self, user_id):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        if user:
            user_dict = dict(user)
            user_dict['achievements_list'] = self.get_user_achievements(user_id)
            return user_dict
        return None

    def authenticate(self, email, password):
        user = self.get_user_by_email(email)
        if user and self.verify_password(password, user['password_hash']):
            return user
        return None

    def update_user(self, user_id, data):
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
            cursor.execute(f'UPDATE users SET {", ".join(updates)} WHERE id = ?', values)
            conn.commit()
        conn.close()
        return self.get_user_by_id(user_id)

    def update_streak(self, user_id, streak):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET streak = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (streak, user_id)
        )
        conn.commit()
        if streak >= 7:
            self.add_achievement(user_id, 'Week Hero')
        if streak >= 30:
            self.add_achievement(user_id, '30 Days')
        if streak >= 100:
            self.add_achievement(user_id, 'Master')
        conn.close()
        return self.get_user_by_id(user_id)

    def add_achievement(self, user_id, achievement_name):
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
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT achievement_name, unlocked_at FROM achievements WHERE user_id = ? ORDER BY unlocked_at DESC',
            (user_id,)
        )
        achievements = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return achievements

    # ----- Ручной ввод экранного времени (старый калькулятор) -----
    def save_screen_time(self, user_id, hours, days):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO screen_time_history (user_id, hours, days) VALUES (?, ?, ?)',
            (user_id, hours, days)
        )
        conn.commit()
        conn.close()

    def get_screen_time_history(self, user_id, limit=30):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM screen_time_history WHERE user_id = ? ORDER BY recorded_at DESC LIMIT ?',
            (user_id, limit)
        )
        history = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return history

    # ----- Отчёты со скриншотами -----
    def save_screen_time_log(self, user_id, image_path, recognized_minutes, reported_date):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO screen_time_logs (user_id, image_path, recognized_minutes, reported_date) VALUES (?, ?, ?, ?)',
            (user_id, image_path, recognized_minutes, reported_date)
        )
        conn.commit()
        log_id = cursor.lastrowid
        conn.close()
        return log_id

    def get_screen_time_logs(self, user_id):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM screen_time_logs WHERE user_id = ? ORDER BY reported_date DESC',
            (user_id,)
        )
        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return logs

    # ----- Очки -----
    def update_points(self, user_id, points_delta, reason=''):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET points = points + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (points_delta, user_id)
        )
        cursor.execute(
            'INSERT INTO points_log (user_id, amount, reason) VALUES (?, ?, ?)',
            (user_id, points_delta, reason)
        )
        conn.commit()
        conn.close()

    def get_points(self, user_id):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT points FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row['points'] if row else 0

    # ----- Челленджи -----
    def get_active_challenges(self):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM challenges WHERE is_active = 1')
        challenges = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return challenges

    def get_user_challenges(self, user_id):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT uc.*, c.name, c.description, c.goal_type, c.goal_value, c.reward_points
            FROM user_challenges uc
            JOIN challenges c ON uc.challenge_id = c.id
            WHERE uc.user_id = ?
        ''', (user_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def join_challenge(self, user_id, challenge_id):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO user_challenges (user_id, challenge_id) VALUES (?, ?)',
                (user_id, challenge_id)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def update_challenge_progress(self, user_id, challenge_id, progress):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE user_challenges SET progress = ? WHERE user_id = ? AND challenge_id = ?',
            (progress, user_id, challenge_id)
        )
        conn.commit()
        conn.close()

    def complete_challenge(self, user_id, challenge_id):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE user_challenges SET completed = 1, completed_at = CURRENT_DATE WHERE user_id = ? AND challenge_id = ?',
            (user_id, challenge_id)
        )
        conn.commit()
        conn.close()

    # ----- Лидерборд -----
    def get_leaderboard(self, limit=50):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, name, points FROM users ORDER BY points DESC LIMIT ?',
            (limit,)
        )
        leaders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return leaders