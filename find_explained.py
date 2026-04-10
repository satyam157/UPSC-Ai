from db import get_connection

conn = get_connection()
if conn:
    try:
        cur = conn.cursor()
        cur.execute("SELECT category, count(*) FROM news WHERE category ILIKE '%explained%' OR title ILIKE '%explained%' GROUP BY category")
        rows = cur.fetchall()
        print("Explained items by category:")
        for r in rows:
            print(f"  {r[0]}: {r[1]} articles")
        
        cur.execute("SELECT id, title, date FROM news WHERE category ILIKE '%explained%' OR title ILIKE '%explained%' ORDER BY date DESC LIMIT 5")
        rows = cur.fetchall()
        print("\nRecent Explained titles:")
        for r in rows:
            print(f"  [{r[2]}] {r[1]}")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
else:
    print("Failed to connect to database.")
