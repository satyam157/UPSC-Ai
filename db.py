import psycopg2
import os
import streamlit as st
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    """Get a fresh database connection with proper error handling."""
    try:
        try:
            if "DATABASE_URL" in st.secrets:
                return psycopg2.connect(st.secrets["DATABASE_URL"])
        except Exception:
            pass

        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return psycopg2.connect(db_url)

        connection = psycopg2.connect(
            dbname=os.getenv("PG_DB", "postgres"),
            user=os.getenv("PG_USER", "postgres"),
            password=os.getenv("PG_PASSWORD", "postgres"),
            host=os.getenv("PG_HOST", "localhost"),
            port=os.getenv("PG_PORT", "5432")
        )
        return connection
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None

def _safe_rollback(connection):
    """Safely rollback a connection if still open."""
    if connection:
        try:
            if not connection.closed:
                connection.rollback()
        except Exception:
            pass

def _init_schema(connection):
    """Initialize database schema."""
    if not connection:
        return
    try:
        with connection.cursor() as cur:
            cur.execute("SET statement_timeout = 60000")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id SERIAL PRIMARY KEY,
                    title TEXT,
                    content TEXT,
                    url TEXT,
                    date TEXT
                )
            """)
            # Fix duplicates before creating unique index
            cur.execute("DELETE FROM news a USING news b WHERE a.id < b.id AND a.title = b.title")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS news_title_uq ON news (title)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    id SERIAL PRIMARY KEY,
                    question TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS results (
                    id SERIAL PRIMARY KEY,
                    name TEXT, 
                    total INT, 
                    attempted INT,
                    correct INT, 
                    wrong INT, 
                    accuracy REAL, 
                    marks REAL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS saved_items (
                    id SERIAL PRIMARY KEY,
                    item_type TEXT,
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    username TEXT PRIMARY KEY,
                    retention_days INT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS ca_filters (
                    id SERIAL PRIMARY KEY,
                    word TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Cleanup duplicates in filters
            cur.execute("DELETE FROM ca_filters a USING ca_filters b WHERE a.id < b.id AND a.word = b.word")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ca_filters_word_uq ON ca_filters (word)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS ai_reports (
                    id SERIAL PRIMARY KEY,
                    report_type TEXT,
                    period_label TEXT,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS test_papers (
                    id SERIAL PRIMARY KEY,
                    test_name TEXT,
                    test_date DATE DEFAULT CURRENT_DATE,
                    total_questions INT,
                    attempted INT,
                    not_attempted INT,
                    guessed_correct INT,
                    guessed_incorrect INT,
                    carelessness_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        connection.commit()
    except Exception as e:
        _safe_rollback(connection)
        print(f"Schema initialization error: {e}")

def get_conn():
    """Get a fresh database connection, initializing schema if needed."""
    conn = get_connection()
    if not conn:
        return None
    try:
        # Test connection is alive
        with conn.cursor() as c:
            c.execute("SELECT 1")
        conn.commit()
        # Initialize schema if needed
        _init_schema(conn)
        return conn
    except Exception as e:
        print(f"Connection check failed: {e}")
        _safe_rollback(conn)
        return None

# ── NEWS ──────────────────────────────────────────────────────────────────────

def insert_news(news):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            for n in news:
                try:
                    c.execute(
                        """
                        INSERT INTO news (title, content, url, date)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (title) DO NOTHING
                        """,
                        (n["title"], n.get("content", ""), n.get("link", ""), n["date"])
                    )
                except Exception:
                    _safe_rollback(conn)
                    c.execute(
                        """
                        INSERT INTO news (title, content, date)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (title) DO NOTHING
                        """,
                        (n["title"], n.get("content", ""), n["date"])
                    )
        conn.commit()
    except Exception as e:
        print(f"Error inserting news: {e}")
        _safe_rollback(conn)

def get_news():
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as c:
            try:
                c.execute("SELECT title, content, date, COALESCE(url, '') FROM news")
            except Exception:
                _safe_rollback(conn)
                c.execute("SELECT title, content, date, '' FROM news")
            return c.fetchall()
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return []

def save_question(q):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO questions (question) VALUES (%s)", (q,))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

def get_questions():
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT question FROM questions")
            return [x[0] for x in c.fetchall()]
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return []

# ── RESULTS ───────────────────────────────────────────────────────────────────

def save_result(data):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO results (name, total, attempted, correct, wrong, accuracy, marks) VALUES (%s, %s, %s, %s, %s, %s, %s)", data)
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

def get_results():
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT id, name, total, attempted, correct, wrong, accuracy, marks FROM results")
            return c.fetchall()
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return []

def delete_result(rowid):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM results WHERE id = %s", (rowid,))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

# ── SAVED ITEMS ───────────────────────────────────────────────────────────────

def save_item(item_type, content):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO saved_items (item_type, content) VALUES (%s, %s)", (item_type, content))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

def get_saved_items():
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT id, item_type, content, timestamp FROM saved_items ORDER BY timestamp DESC")
            return c.fetchall()
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return []

def delete_saved_item(item_id):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM saved_items WHERE id = %s", (item_id,))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

def clean_old(days=15):
    conn = get_conn()
    if not conn: return
    try:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        with conn.cursor() as c:
            c.execute("DELETE FROM news WHERE date < %s", (cutoff,))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

# ── USER SETTINGS ─────────────────────────────────────────────────────────────

def get_retention(username):
    conn = get_conn()
    if not conn: return 15
    try:
        with conn.cursor() as c:
            c.execute("SELECT retention_days FROM user_settings WHERE username = %s", (username,))
            res = c.fetchone()
            if res:
                return res[0]
            return 15
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return 15

def set_retention(username, days):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("""
            INSERT INTO user_settings (username, retention_days)
            VALUES (%s, %s)
            ON CONFLICT (username) DO UPDATE 
            SET retention_days = EXCLUDED.retention_days
            """, (username, days))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

# ── CA FILTERS ────────────────────────────────────────────────────────────────

def add_ca_filter(word):
    conn = get_conn()
    if not conn: return False
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO ca_filters (word) VALUES (%s) ON CONFLICT (word) DO NOTHING", (word.lower().strip(),))
        conn.commit()
        return True
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return False

def get_ca_filters():
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT id, word FROM ca_filters ORDER BY word")
            return c.fetchall()
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return []

def delete_ca_filter(filter_id):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM ca_filters WHERE id = %s", (filter_id,))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

# ── AI REPORTS ────────────────────────────────────────────────────────────────

def save_ai_report(report_type, period_label, content):
    conn = get_conn()
    if not conn: return None
    try:
        with conn.cursor() as c:
            c.execute(
                "INSERT INTO ai_reports (report_type, period_label, content) VALUES (%s, %s, %s) RETURNING id",
                (report_type, period_label, content)
            )
            new_id = c.fetchone()[0]
        conn.commit()
        return new_id
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return None

def get_ai_reports():
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT id, report_type, period_label, content, created_at FROM ai_reports ORDER BY created_at DESC")
            return c.fetchall()
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return []

def delete_ai_report(report_id):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM ai_reports WHERE id = %s", (report_id,))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

# ── TEST PAPERS ───────────────────────────────────────────────────────────────

def save_test_paper(test_name, test_date, total_questions, attempted, not_attempted,
                    guessed_correct, guessed_incorrect, carelessness_notes):
    conn = get_conn()
    if not conn: return None
    try:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO test_papers 
                (test_name, test_date, total_questions, attempted, not_attempted,
                 guessed_correct, guessed_incorrect, carelessness_notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """, (test_name, test_date, total_questions, attempted, not_attempted,
                  guessed_correct, guessed_incorrect, carelessness_notes))
            new_id = c.fetchone()[0]
        conn.commit()
        return new_id
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return None

def get_test_papers():
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT id, test_name, test_date, total_questions, attempted, not_attempted,
                       guessed_correct, guessed_incorrect, carelessness_notes, created_at
                FROM test_papers ORDER BY test_date DESC, created_at DESC
            """)
            return c.fetchall()
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return []

def delete_test_paper(paper_id):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM test_papers WHERE id = %s", (paper_id,))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)
