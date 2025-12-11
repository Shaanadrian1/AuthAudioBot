"""
SQLite Database for TTS Bot
"""

import sqlite3
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import random
import string

logger = logging.getLogger(__name__)

class Database:
    """Database manager"""
    
    def __init__(self, db_path="data/tts_bot.db"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create directories if needed
        import os
        os.makedirs("data", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                access_code TEXT,
                quota_total INTEGER DEFAULT 0,
                quota_used INTEGER DEFAULT 0,
                quota_remaining INTEGER GENERATED ALWAYS AS (quota_total - quota_used) VIRTUAL,
                voice_id TEXT DEFAULT 'moss_audio_4d4208c8-b67d-11f0-afaf-868268514f62',
                speed REAL DEFAULT 0.9,
                pitch INTEGER DEFAULT 0,
                volume REAL DEFAULT 1.6,
                emotion TEXT DEFAULT 'auto',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Access codes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS access_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                quota_total INTEGER NOT NULL,
                quota_used INTEGER DEFAULT 0,
                quota_remaining INTEGER GENERATED ALWAYS AS (quota_total - quota_used) VIRTUAL,
                max_users INTEGER DEFAULT 1,
                current_users INTEGER DEFAULT 0,
                expiry_days INTEGER DEFAULT 30,
                expiry_date TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                created_by TEXT DEFAULT 'admin',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Voice models table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS voice_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                voice_id TEXT UNIQUE NOT NULL,
                model TEXT DEFAULT 'speech-2.6-turbo',
                language TEXT DEFAULT 'en',
                gender TEXT,
                preview_url TEXT,
                image_url TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Usage history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                char_count INTEGER,
                voice_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_codes_code ON access_codes(code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_user_date ON usage_history(user_id, created_at)')
        
        # Insert default voice if not exists
        cursor.execute('''
            INSERT OR IGNORE INTO voice_models 
            (name, voice_id, model, language, gender, image_url) 
            VALUES 
            ('Moss Audio (Turbo)', 'moss_audio_4d4208c8-b67d-11f0-afaf-868268514f62', 
             'speech-2.6-turbo', 'en', 'male', 'https://i.imgur.com/gBqjH3S.png')
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Database initialized")
    
    async def add_user(self, telegram_id: int, username: str, 
                      first_name: str, last_name: str = None) -> bool:
        """Add or update user"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO users 
                (telegram_id, username, first_name, last_name, last_active)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (telegram_id, username, first_name, last_name))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False
    
    async def get_user_quota(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get user quota information"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT u.access_code, u.quota_total, u.quota_used, u.quota_remaining,
                       ac.expiry_date, ac.is_active
                FROM users u
                LEFT JOIN access_codes ac ON u.access_code = ac.code
                WHERE u.telegram_id = ?
            ''', (telegram_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            return {
                'code': row['access_code'],
                'total': row['quota_total'],
                'used': row['quota_used'],
                'remaining': row['quota_remaining'],
                'expiry': row['expiry_date'],
                'is_active': bool(row['is_active'])
            }
            
        except Exception as e:
            logger.error(f"Error getting user quota: {e}")
            return None
    
    async def activate_access_code(self, telegram_id: int, code: str) -> Dict[str, Any]:
        """Activate access code for user"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Check if code exists and is valid
            cursor.execute('''
                SELECT * FROM access_codes 
                WHERE code = ? AND is_active = 1
            ''', (code,))
            
            code_data = cursor.fetchone()
            
            if not code_data:
                conn.close()
                return {
                    'success': False,
                    'message': 'Invalid or inactive access code'
                }
            
            # Check expiry
            if code_data['expiry_date']:
                expiry = datetime.fromisoformat(code_data['expiry_date'])
                if datetime.now() > expiry:
                    conn.close()
                    return {
                        'success': False,
                        'message': 'Access code has expired'
                    }
            
            # Check user limit
            if code_data['max_users'] > 0 and code_data['current_users'] >= code_data['max_users']:
                conn.close()
                return {
                    'success': False,
                    'message': 'Access code user limit reached'
                }
            
            # Update user with access code
            cursor.execute('''
                UPDATE users 
                SET access_code = ?, 
                    quota_total = ?,
                    quota_used = 0
                WHERE telegram_id = ?
            ''', (code, code_data['quota_total'], telegram_id))
            
            # Update access code usage
            cursor.execute('''
                UPDATE access_codes 
                SET current_users = current_users + 1,
                    quota_used = quota_used + ?
                WHERE code = ?
            ''', (code_data['quota_total'], code))
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'message': 'Access code activated',
                'quota': code_data['quota_total'],
                'expiry': code_data['expiry_date']
            }
            
        except Exception as e:
            logger.error(f"Error activating access code: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    async def use_quota(self, telegram_id: int, char_count: int) -> bool:
        """Use quota from user"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE users 
                SET quota_used = quota_used + ?
                WHERE telegram_id = ? AND quota_remaining >= ?
            ''', (char_count, telegram_id, char_count))
            
            affected = cursor.rowcount
            
            if affected > 0:
                # Also update access code usage
                cursor.execute('''
                    UPDATE access_codes ac
                    SET quota_used = quota_used + ?
                    FROM users u
                    WHERE u.telegram_id = ? 
                      AND ac.code = u.access_code
                ''', (char_count, telegram_id))
            
            conn.commit()
            conn.close()
            
            return affected > 0
            
        except Exception as e:
            logger.error(f"Error using quota: {e}")
            return False
    
    async def get_user_settings(self, telegram_id: int) -> Dict[str, Any]:
        """Get user TTS settings"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT voice_id, speed, pitch, volume, emotion
                FROM users 
                WHERE telegram_id = ?
            ''', (telegram_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            else:
                # Default settings
                return {
                    'voice_id': 'moss_audio_4d4208c8-b67d-11f0-afaf-868268514f62',
                    'speed': 0.9,
                    'pitch': 0,
                    'volume': 1.6,
                    'emotion': 'auto'
                }
                
        except Exception as e:
            logger.error(f"Error getting user settings: {e}")
            return {}
    
    async def get_all_voices(self) -> List[Dict[str, Any]]:
        """Get all voice models"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT name, voice_id, model, language, gender, image_url
                FROM voice_models 
                WHERE is_active = 1
                ORDER BY name
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting voices: {e}")
            return []
    
    async def add_voice(self, voice_data: Dict[str, Any]) -> bool:
        """Add new voice model"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO voice_models 
                (name, voice_id, model, language, gender, preview_url, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                voice_data['name'],
                voice_data['voice_id'],
                voice_data.get('model', 'speech-2.6-turbo'),
                voice_data.get('language', 'en'),
                voice_data.get('gender'),
                voice_data.get('preview_url'),
                voice_data.get('image_url')
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error adding voice: {e}")
            return False
    
    async def add_history(self, user_id: int, text: str, 
                         char_count: int, voice_id: str) -> bool:
        """Add usage history"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Get user database ID
            cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (user_id,))
            user = cursor.fetchone()
            
            if not user:
                conn.close()
                return False
            
            cursor.execute('''
                INSERT INTO usage_history 
                (user_id, text, char_count, voice_id)
                VALUES (?, ?, ?, ?)
            ''', (user['id'], text, char_count, voice_id))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error adding history: {e}")
            return False
    
    def create_access_code(self, quota: int, days: int = 30, 
                          max_users: int = 1, notes: str = None) -> str:
        """Create new access code"""
        try:
            # Generate random code
            letters = string.ascii_uppercase + string.digits
            random_part = ''.join(random.choices(letters, k=15))
            code = f"TTS-{random_part}"
            
            # Calculate expiry date
            expiry_date = datetime.now() + timedelta(days=days)
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO access_codes 
                (code, quota_total, max_users, expiry_date, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (code, quota, max_users, expiry_date, notes))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Access code created: {code}")
            return code
            
        except Exception as e:
            logger.error(f"Error creating access code: {e}")
            return None
    
    def get_all_codes(self) -> List[Dict[str, Any]]:
        """Get all access codes"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM access_codes 
                ORDER BY created_at DESC
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting codes: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get system statistics"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Total users
            cursor.execute('SELECT COUNT(*) as count FROM users')
            total_users = cursor.fetchone()['count']
            
            # Active users (last 30 days)
            cursor.execute('''
                SELECT COUNT(DISTINCT user_id) as count 
                FROM usage_history 
                WHERE created_at >= datetime('now', '-30 days')
            ''')
            active_users = cursor.fetchone()['count']
            
            # Total usage
            cursor.execute('SELECT SUM(char_count) as total FROM usage_history')
            total_chars = cursor.fetchone()['total'] or 0
            
            # Daily usage (last 7 days)
            cursor.execute('''
                SELECT date(created_at) as date, 
                       SUM(char_count) as chars,
                       COUNT(*) as requests
                FROM usage_history 
                WHERE created_at >= datetime('now', '-7 days')
                GROUP BY date(created_at)
                ORDER BY date DESC
            ''')
            daily_usage = [dict(row) for row in cursor.fetchall()]
            
            # Voice usage
            cursor.execute('''
                SELECT voice_id, 
                       SUM(char_count) as chars,
                       COUNT(*) as requests
                FROM usage_history 
                GROUP BY voice_id
                ORDER BY chars DESC
                LIMIT 10
            ''')
            voice_usage = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'total_characters': total_chars,
                'daily_usage': daily_usage,
                'voice_usage': voice_usage,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    def health_check(self) -> bool:
        """Check database health"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            conn.close()
            return True
        except:
            return False
    
    def init_database(self):
        """Initialize database (wrapper for init_db)"""
        self.init_db()