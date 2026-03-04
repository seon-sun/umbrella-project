import sqlite3

conn = sqlite3.connect("umbrellas.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS umbrellas (
    id INTEGER PRIMARY KEY,
    status TEXT,
    student_id TEXT
)
""")

cur.execute("DELETE FROM umbrellas")

for i in range(1, 31):
    cur.execute("INSERT INTO umbrellas (id, status, student_id) VALUES (?, 'available', NULL)", (i,))

conn.commit()
conn.close()

print("DB 재생성 완료")