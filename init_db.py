import sqlite3

conn = sqlite3.connect("umbrellas.db")
cur = conn.cursor()

# 기존 테이블 삭제
cur.execute("DROP TABLE IF EXISTS umbrellas")

# 테이블 생성
cur.execute("""
CREATE TABLE umbrellas (
    id INTEGER PRIMARY KEY,
    status TEXT,
    student_id TEXT
)
""")

# 우산 30개 생성
for i in range(1, 31):
    cur.execute(
        "INSERT INTO umbrellas (id, status, student_id) VALUES (?, 'available', NULL)",
        (i,)
    )

conn.commit()
conn.close()
print("DB 초기화 완료 (1~30번 우산)")