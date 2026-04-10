"""One-time script: revoke news fetch access for all users."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

conn = db.get_connection()
if not conn:
    print("ERROR: Could not connect to database.")
    exit(1)

cur = conn.cursor()

# Ensure column exists (matches schema init in db.py)
cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS has_news_access BOOLEAN DEFAULT FALSE")
conn.commit()

cur.execute("UPDATE users SET has_news_access = FALSE")
conn.commit()

cur.execute("SELECT username, has_news_access FROM users")
rows = cur.fetchall()
print("Updated users:")
for r in rows:
    print(f"  {r[0]:20s}  has_news_access = {r[1]}")
conn.close()
print("\nDone - all users are now restricted.")
