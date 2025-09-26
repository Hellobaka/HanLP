# -*- coding:utf-8 -*-
# Author: Claude Code
# Date: 2025-09-25
"""
Database module for HanLP RESTful API Server
Handles SQLite database operations for token management and statistics.
"""

import sqlite3
import os
import time
from typing import Optional, List, Tuple


class TokenDB:
    """SQLite database for token management and statistics"""

    def __init__(self, db_path: str = "tokens.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize the database and create tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create tokens table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT UNIQUE NOT NULL,
                    applicant_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_valid BOOLEAN DEFAULT 1,
                    usage_count INTEGER DEFAULT 0,
                    char_count INTEGER DEFAULT 0,
                    is_admin BOOLEAN DEFAULT 0
                )
            ''')

            # Create index on token for faster lookups
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_token ON tokens(token)
            ''')

            # Create index on applicant_id for faster lookups
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_applicant ON tokens(applicant_id)
            ''')

            conn.commit()

    def add_token(self, token: str, applicant_id: int, is_admin: bool = False) -> bool:
        """Add a new token to the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO tokens (token, applicant_id, is_admin)
                    VALUES (?, ?, ?)
                ''', (token, applicant_id, is_admin))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            # Token already exists
            return False
        except Exception:
            return False

    def get_token_info(self, token: str) -> Optional[Tuple]:
        """Get token information by token value"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, token, applicant_id, is_valid, usage_count, char_count, is_admin
                FROM tokens
                WHERE token = ?
            ''', (token,))
            return cursor.fetchone()

    def is_valid_token(self, token: str) -> bool:
        """Check if a token is valid"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT is_valid FROM tokens WHERE token = ?
            ''', (token,))
            result = cursor.fetchone()
            return result and result[0] == 1

    def is_admin_token(self, token: str) -> bool:
        """Check if a token is an admin token"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT is_admin FROM tokens WHERE token = ?
            ''', (token,))
            result = cursor.fetchone()
            return result and result[0] == 1

    def invalidate_token(self, token: str) -> bool:
        """Invalidate a token"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE tokens SET is_valid = 0 WHERE token = ?
            ''', (token,))
            conn.commit()
            return cursor.rowcount > 0

    def get_tokens_by_applicant(self, user_id: int) -> List[Tuple]:
        """Get all tokens for a specific user"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, token, created_at, is_valid, usage_count, char_count
                FROM tokens
                WHERE applicant_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))
            return cursor.fetchall()

    def invalidate_tokens_by_applicant(self, user_id: int) -> int:
        """Invalidate all tokens for a specific user"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE tokens SET is_valid = 0 WHERE applicant_id = ?
            ''', (user_id,))
            conn.commit()
            return cursor.rowcount

    def add_token_usage(self, token: str, char_count: int) -> bool:
        """Add usage statistics for a token"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE tokens
                SET usage_count = usage_count + 1, char_count = char_count + ?
                WHERE token = ? AND is_valid = 1
            ''', (char_count, token))
            conn.commit()
            return cursor.rowcount > 0

    def get_all_tokens_stats(self) -> List[Tuple]:
        """Get statistics for all tokens (for admin use)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT token, applicant_id, created_at, usage_count, char_count, is_valid, is_admin
                FROM tokens
                ORDER BY usage_count DESC
            ''')
            return cursor.fetchall()

    def delete_token(self, token: str) -> bool:
        """Delete a token from the database (admin only)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM tokens WHERE token = ?
            ''', (token,))
            conn.commit()
            return cursor.rowcount > 0

    def get_valid_tokens(self) -> List[str]:
        """Get all valid tokens"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT token FROM tokens WHERE is_valid = 1
            ''')
            return [row[0] for row in cursor.fetchall()]