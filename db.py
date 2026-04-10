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
                    source TEXT,
                    category TEXT,
                    date TEXT
                )
            """)
            # Ensure columns exist if table was already created
            cur.execute("ALTER TABLE news ADD COLUMN IF NOT EXISTS url TEXT")
            cur.execute("ALTER TABLE news ADD COLUMN IF NOT EXISTS source TEXT")
            cur.execute("ALTER TABLE news ADD COLUMN IF NOT EXISTS category TEXT")
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
            
            # URL Summaries (Article Summarizer)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS url_summaries (
                    id SERIAL PRIMARY KEY,
                    url VARCHAR(1000) UNIQUE,
                    title VARCHAR(500),
                    subject VARCHAR(250),
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Syllabus Quizzes
            cur.execute("""
                CREATE TABLE IF NOT EXISTS syllabus_quizzes (
                    id SERIAL PRIMARY KEY,
                    subject VARCHAR(250),
                    source VARCHAR(100),
                    questions JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Syllabus Quiz Attempts
            cur.execute("""
                CREATE TABLE IF NOT EXISTS syllabus_quiz_attempts (
                    id SERIAL PRIMARY KEY,
                    quiz_id INTEGER,
                    user_answers JSONB,
                    score INTEGER,
                    percentage INTEGER,
                    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (quiz_id) REFERENCES syllabus_quizzes(id) ON DELETE CASCADE
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
    """Insert news items using executemany for efficiency."""
    if not news:
        return 0
    
    conn = get_connection()
    if not conn:
        return 0
    
    inserted_count = 0
    try:
        with conn.cursor() as c:
            # Prepare data for executemany
            data = [
                (n.get("title", ""), n.get("content", ""), n.get("url", ""), n.get("source", ""), n.get("category", "General"), n.get("date", ""))
                for n in news
            ]
            
            # executemany is more efficient than looping
            c.executemany(
                """
                INSERT INTO news (title, content, url, source, category, date)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (title) DO NOTHING
                """,
                data
            )
            inserted_count = c.rowcount
        
        conn.commit()
        return inserted_count
    except Exception as e:
        print(f"Insert error: {e}")
        _safe_rollback(conn)
        return 0
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

def get_news():
    """Retrieve recent news from database, ordered by date (newest first). Limited to 500 items for performance."""
    conn = get_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor() as c:
            # Retrieve all relevant news fields including category
            c.execute("SELECT title, content, date, url, source, category FROM news ORDER BY date DESC, id DESC LIMIT 600")
            return c.fetchall()
    except Exception as e:
        print(f"Error retrieving news: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_news_with_ids():
    """
    Like get_news() but includes the primary key `id` as the first column.
    Used by the DB audit so noise can be purged safely by PK.

    Returns rows: (id, title, content, date, url, source, category)
    """
    conn = get_connection()
    if not conn:
        return []

    try:
        with conn.cursor() as c:
            c.execute(
                "SELECT id, title, content, date, url, source, category "
                "FROM news ORDER BY date DESC, id DESC LIMIT 600"
            )
            return c.fetchall()
    except Exception as e:
        print(f"Error retrieving news with IDs: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def delete_news_by_ids(ids: list) -> int:
    """
    Delete news articles by their primary key IDs.
    Returns the number of rows actually deleted.

    This is safer than deleting by title (avoids accidental multi-row deletes
    when two articles share identical truncated titles).
    """
    if not ids:
        return 0

    conn = get_connection()
    if not conn:
        return 0

    try:
        with conn.cursor() as c:
            # Use a single parameterised IN query for efficiency
            placeholders = ",".join(["%s"] * len(ids))
            c.execute(f"DELETE FROM news WHERE id IN ({placeholders})", ids)
            deleted = c.rowcount
        conn.commit()
        return deleted
    except Exception as e:
        print(f"Error deleting news by IDs: {e}")
        _safe_rollback(conn)
        return 0
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass



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

# ── SYLLABUS SUMMARIES (Yojana, Kurukshetra, Economic Survey, Budget, Yearbook) ──

def save_syllabus_summary(resource_type, title, content, source_url=""):
    """Save a syllabus resource summary (Yojana, Kurukshetra, etc.)"""
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS syllabus_summaries (
                    id SERIAL PRIMARY KEY,
                    resource_type TEXT,
                    title TEXT,
                    content TEXT,
                    source_url TEXT,
                    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            c.execute(
                """
                INSERT INTO syllabus_summaries (resource_type, title, content, source_url)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (resource_type, title, content, source_url)
            )
            result_id = c.fetchone()[0]
        conn.commit()
        return result_id
    except Exception as e:
        print(f"Error saving syllabus summary: {e}")
        _safe_rollback(conn)
        return None
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

def get_syllabus_summaries(resource_type=None):
    """Get syllabus summaries, optionally filtered by resource type"""
    conn = get_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor() as c:
            if resource_type:
                c.execute(
                    """
                    SELECT id, resource_type, title, content, source_url, saved_at
                    FROM syllabus_summaries
                    WHERE resource_type = %s
                    ORDER BY saved_at DESC
                    LIMIT 100
                    """,
                    (resource_type,)
                )
            else:
                c.execute(
                    """
                    SELECT id, resource_type, title, content, source_url, saved_at
                    FROM syllabus_summaries
                    ORDER BY saved_at DESC
                    LIMIT 200
                    """
                )
            return c.fetchall()
    except Exception as e:
        print(f"Error retrieving syllabus summaries: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

def delete_syllabus_summary(summary_id):
    """Delete a syllabus summary"""
    conn = get_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM syllabus_summaries WHERE id = %s", (summary_id,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"Error deleting syllabus summary: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


# ════════════════════════════════════════════════════════════════════════════
# SYLLABUS QUIZ FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def save_syllabus_quiz(subject, questions_json, source="Article Summary"):
    """
    Save a quiz generated from an article summary
    Returns: quiz_id
    """
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO syllabus_quizzes (subject, source, questions)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (subject, source, questions_json))
            
            quiz_id = c.fetchone()[0]
        conn.commit()
        return quiz_id
    except Exception as e:
        print(f"Error saving syllabus quiz: {e}")
        _safe_rollback(conn)
        return None
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_syllabus_quiz(quiz_id):
    """Get a specific quiz"""
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT id, resource_type, summary_id, questions, created_at
                FROM syllabus_quizzes WHERE id = %s
            """, (quiz_id,))
            
            result = c.fetchone()
            return result
    except Exception as e:
        print(f"Error fetching syllabus quiz: {e}")
        return None
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def save_quiz_attempt(quiz_id, user_answers, score, percentage):
    """
    Save a quiz attempt/result
    Returns: attempt_id
    """
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO syllabus_quiz_attempts (quiz_id, user_answers, score, percentage)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (quiz_id, user_answers, score, percentage))
            
            attempt_id = c.fetchone()[0]
        conn.commit()
        return attempt_id
    except Exception as e:
        print(f"Error saving quiz attempt: {e}")
        _safe_rollback(conn)
        return None
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_quiz_attempts(quiz_id, limit=10):
    """Get all attempts for a quiz"""
    conn = get_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT id, quiz_id, user_answers, score, percentage, attempted_at
                FROM syllabus_quiz_attempts
                WHERE quiz_id = %s
                ORDER BY attempted_at DESC
                LIMIT %s
            """, (quiz_id, limit))
            
            results = c.fetchall()
            return results
    except Exception as e:
        print(f"Error fetching quiz attempts: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def delete_syllabus_quiz(quiz_id):
    """Delete a quiz and all its attempts"""
    conn = get_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as c:
            # Delete attempts first (due to foreign key)
            c.execute("DELETE FROM syllabus_quiz_attempts WHERE quiz_id = %s", (quiz_id,))
            # Delete quiz
            c.execute("DELETE FROM syllabus_quizzes WHERE id = %s", (quiz_id,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"Error deleting syllabus quiz: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


# ════════════════════════════════════════════════════════════════════════════
# URL SUMMARY STORAGE
# ════════════════════════════════════════════════════════════════════════════

def save_url_summary(url, title, summary, subject=""):
    """
    Save a URL summary from the URL Summarizer tool
    Returns: summary_id
    """
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO url_summaries (url, title, subject, summary)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (url) DO UPDATE SET
                    title = EXCLUDED.title,
                    subject = EXCLUDED.subject,
                    summary = EXCLUDED.summary
                RETURNING id
            """, (url, title, subject, summary))
            
            summary_id = c.fetchone()[0]
        conn.commit()
        return summary_id
    except Exception as e:
        print(f"Error saving URL summary: {e}")
        _safe_rollback(conn)
        return None
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_url_summaries(limit=50):
    """Get all saved URL summaries"""
    conn = get_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT id, url, title, subject, summary, created_at
                FROM url_summaries
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            
            results = c.fetchall()
            return results
    except Exception as e:
        print(f"Error fetching URL summaries: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def delete_url_summary(summary_id):
    """Delete a URL summary"""
    conn = get_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM url_summaries WHERE id = %s", (summary_id,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"Error deleting URL summary: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass
