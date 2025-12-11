"""
Simplified Database for Render
"""

import sqlite3
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path="data/tts_bot.db"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Get database connection"""
        # Create data directory if not exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS access_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                quota_total INTEGER DEFAULT 50000,
                quota_used INTEGER DEFAULT 0,
                expiry_date DATETIME,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS voice_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                voice_id TEXT UNIQUE NOT NULL,
                model TEXT DEFAULT 'speech-2.6-turbo',
                language TEXT DEFAULT 'en',
                gender TEXT,
                image_url TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default voice
        cursor.execute('''
            INSERT OR IGNORE INTO voice_models 
            (name, voice_id, model, language, gender, image_url)
            VALUES 
            ('Moss Audio (Turbo)', 'moss_audio_4d4208c8-b67d-11f0-afaf-868268514f62', 
             'speech-2.6-turbo', 'en', 'male', 'https://i.imgur.com/gBqjH3S.png')
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def create_access_code(self, quota=50000, days=30):
        """Create new access code"""
        import random
        import string
        
        # Generate random code
        code = f"TTS-{''.join(random.choices(string.ascii_uppercase + string.digits, k=15))}"
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Calculate expiry date
        from datetime import datetime, timedelta
        expiry_date = datetime.now() + timedelta(days=days)
        
        cursor.execute('''
            INSERT INTO access_codes (code, quota_total, expiry_date)
            VALUES (?, ?, ?)
        ''', (code, quota, expiry_date))
        
        conn.commit()
        conn.close()
        
        return code
    
    def get_all_codes(self):
        """Get all access codes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM access_codes ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_all_voices(self):
        """Get all voice models"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM voice_models ORDER BY name')
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def add_voice(self, name, voice_id, model="speech-2.6-turbo", language="en", gender=None, image_url=None):
        """Add new voice model"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO voice_models (name, voice_id, model, language, gender, image_url)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, voice_id, model, language, gender, image_url))
        
        conn.commit()
        conn.close()
        return True
