# -*- coding: utf-8 -*-
import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from movies_seed import INITIAL_MOVIES

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kino_bot.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # 1. Kinolar jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            year TEXT DEFAULT '2024',
            genre TEXT DEFAULT 'Jangari, Drama',
            country TEXT DEFAULT 'AQSH',
            language TEXT DEFAULT 'O''zbek tilida (Full HD)',
            duration TEXT DEFAULT '2 soat',
            rating TEXT DEFAULT '9.0/10',
            description TEXT DEFAULT '',
            file_id TEXT DEFAULT '',
            views INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. Foydalanuvchilar jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT DEFAULT '',
            username TEXT DEFAULT '',
            is_admin INTEGER DEFAULT 0,
            sub_verified INTEGER DEFAULT 0,
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        cur.execute("ALTER TABLE users ADD COLUMN sub_verified INTEGER DEFAULT 0")
    except Exception:
        pass

    # 3. Majburiy obuna va kino kodlari kanallari jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            invite_link TEXT NOT NULL
        )
    """)

    # Standart majburiy obuna kanalini qo'shish: https://t.me/kinolar_botttt
    cur.execute("""
        INSERT OR IGNORE INTO channels (channel_id, title, invite_link)
        VALUES ('@kinolar_botttt', 'Kinolar bot', 'https://t.me/kinolar_botttt')
    """)

    # 4. Sozlamalar jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Standart admin parolini o'rnatish: abdu8811
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('admin_password', 'abdu8811')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('demo_file_id', '')")

    # Boshlang'ich 100 ta kinoni bazaga qo'shish (agar hali yo'q bo'lsa)
    cur.execute("SELECT COUNT(*) as cnt FROM movies")
    count = cur.fetchone()["cnt"]
    if count == 0:
        for m in INITIAL_MOVIES:
            cur.execute("""
                INSERT OR IGNORE INTO movies
                (code, title, year, genre, country, language, duration, rating, description, file_id, views)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(m["code"]),
                m["title"],
                m.get("year", "2023"),
                m.get("genre", "Jangari"),
                m.get("country", "AQSH"),
                m.get("language", "O'zbek tilida (Full HD)"),
                m.get("duration", "2 soat"),
                m.get("rating", "9.0/10"),
                m.get("description", ""),
                "",
                0
            ))

    conn.commit()
    conn.close()


# ================= FOYDALANUVCHILAR BILAN ISHLASH =================

def register_user(user_id: int, full_name: str, username: str = ""):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        INSERT INTO users (user_id, full_name, username, joined_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            full_name = excluded.full_name,
            username = excluded.username
    """, (user_id, full_name or "", username or "", now))
    conn.commit()
    conn.close()


def set_admin(user_id: int, status: bool = True):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_admin = ? WHERE user_id = ?", (1 if status else 0, user_id))
    conn.commit()
    conn.close()


def is_user_admin(user_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row and row["is_admin"] == 1)


def set_sub_verified(user_id: int, status: bool = True):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET sub_verified = ? WHERE user_id = ?", (1 if status else 0, user_id))
    conn.commit()
    conn.close()


def is_sub_verified(user_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT sub_verified FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row and row["sub_verified"] == 1)


def get_all_users() -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users ORDER BY joined_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ================= KINOLAR BILAN ISHLASH =================

def get_movie_by_code(code: str) -> Optional[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    clean_code = str(code).strip().lstrip("#")
    cur.execute("SELECT * FROM movies WHERE code = ?", (clean_code,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def increment_movie_views(code: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    clean_code = str(code).strip().lstrip("#")
    cur.execute("UPDATE movies SET views = views + 1 WHERE code = ?", (clean_code,))
    conn.commit()
    cur.execute("SELECT views FROM movies WHERE code = ?", (clean_code,))
    row = cur.fetchone()
    conn.close()
    return row["views"] if row else 1


def search_movies_by_title(query: str, limit: int = 15) -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    q = f"%{query.strip()}%"
    cur.execute("""
        SELECT * FROM movies
        WHERE title LIKE ? OR genre LIKE ? OR description LIKE ?
        ORDER BY CAST(code AS INTEGER) ASC, code ASC
        LIMIT ?
    """, (q, q, q, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_all_movies() -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM movies ORDER BY CAST(code AS INTEGER) ASC, code ASC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_top_movies(limit: int = 10) -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM movies ORDER BY views DESC, CAST(code AS INTEGER) ASC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def add_or_update_movie(
    code: str,
    title: str,
    year: str = "2024",
    genre: str = "Jangari, Drama",
    country: str = "AQSH",
    language: str = "O'zbek tilida (Full HD)",
    duration: str = "2 soat",
    rating: str = "9.0/10",
    description: str = "",
    file_id: str = ""
):
    conn = get_conn()
    cur = conn.cursor()
    clean_code = str(code).strip().lstrip("#")
    existing = get_movie_by_code(clean_code)
    if existing:
        cur.execute("""
            UPDATE movies SET
                title = ?,
                year = ?,
                genre = ?,
                country = ?,
                language = ?,
                duration = ?,
                rating = ?,
                description = ?,
                file_id = ?
            WHERE code = ?
        """, (
            title or existing["title"],
            year or existing["year"],
            genre or existing["genre"],
            country or existing["country"],
            language or existing["language"],
            duration or existing["duration"],
            rating or existing["rating"],
            description if description != "" else existing["description"],
            file_id if file_id != "" else existing["file_id"],
            clean_code
        ))
    else:
        cur.execute("""
            INSERT INTO movies
            (code, title, year, genre, country, language, duration, rating, description, file_id, views)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (clean_code, title, year, genre, country, language, duration, rating, description, file_id))
    conn.commit()
    conn.close()


def update_movie_file_id(code: str, file_id: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    clean_code = str(code).strip().lstrip("#")
    cur.execute("UPDATE movies SET file_id = ? WHERE code = ?", (file_id, clean_code))
    updated = cur.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def delete_movie(code: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    clean_code = str(code).strip().lstrip("#")
    cur.execute("DELETE FROM movies WHERE code = ?", (clean_code,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_next_available_code() -> str:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT MAX(CAST(code AS INTEGER)) as max_code FROM movies")
    row = cur.fetchone()
    conn.close()
    max_code = row["max_code"] if row and row["max_code"] is not None else 100
    return str(int(max_code) + 1)


# ================= KANALLAR (MAJBURIY OBUNA) BILAN ISHLASH =================

def get_channels() -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM channels ORDER BY id ASC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def add_channel(channel_id: str, title: str, invite_link: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO channels (channel_id, title, invite_link)
        VALUES (?, ?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET
            title = excluded.title,
            invite_link = excluded.invite_link
    """, (channel_id.strip(), title.strip(), invite_link.strip()))
    conn.commit()
    conn.close()


def remove_channel(db_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM channels WHERE id = ?", (db_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ================= SOZLAMALAR VA STATISTIKA =================

def get_setting(key: str, default: str = "") -> str:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    conn.commit()
    conn.close()


def get_stats() -> Dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as total_users FROM users")
    total_users = cur.fetchone()["total_users"]

    cur.execute("SELECT COUNT(*) as total_movies FROM movies")
    total_movies = cur.fetchone()["total_movies"]

    cur.execute("SELECT COUNT(*) as uploaded_videos FROM movies WHERE file_id != ''")
    uploaded_videos = cur.fetchone()["uploaded_videos"]

    cur.execute("SELECT SUM(views) as total_views FROM movies")
    total_views = cur.fetchone()["total_views"] or 0

    cur.execute("SELECT COUNT(*) as total_channels FROM channels")
    total_channels = cur.fetchone()["total_channels"]

    conn.close()
    return {
        "total_users": total_users,
        "total_movies": total_movies,
        "uploaded_videos": uploaded_videos,
        "total_views": total_views,
        "total_channels": total_channels
    }
