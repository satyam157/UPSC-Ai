from db import get_connection

conn = get_connection()
if conn:
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT LEFT(date, 10) as d, category, count(*) 
            FROM news 
            WHERE date >= '2026-05-06'
            GROUP BY d, category 
            ORDER BY d DESC, count(*) DESC
        """)
        rows = cur.fetchall()
        print("News categories for recent dates:")
        for r in rows:
            print(f"  {r[0]} | {r[1]}: {r[2]} articles")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
else:
    print("Failed to connect to database.")
