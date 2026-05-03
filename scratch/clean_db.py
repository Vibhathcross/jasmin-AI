import sqlite3
import os

db_path = r"c:\Users\USER\.gemini\antigravity\scratch\Jasmin\calendar_memory.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM special_dates")
    rows = cursor.fetchall()
    print("Database Contents:")
    for row in rows:
        print(row)
    
    # Clean up empty specialities
    cursor.execute("DELETE FROM special_dates WHERE speciality IS NULL OR speciality = ''")
    print(f"Deleted {conn.total_changes} invalid rows.")
    conn.commit()
    conn.close()
else:
    print("Database not found.")
