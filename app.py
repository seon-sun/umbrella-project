from flask import Flask, request, redirect
import sqlite3

app = Flask(__name__)

def get_db():
    conn = sqlite3.connect("umbrellas.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/u/<int:num>", methods=["GET", "POST"])
def umbrella(num):
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        student_id = request.form.get("student_id")

        cur.execute("SELECT status, student_id FROM umbrellas WHERE id=?", (num,))
        umbrella = cur.fetchone()

        if umbrella["status"] == "available":
            # 대여
            cur.execute(
                "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                (student_id, num)
            )
        else:
            # 반납 (빌린 사람만 가능)
            if umbrella["student_id"] == student_id:
                cur.execute(
                    "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                    (num,)
                )
            else:
                return "이 우산을 빌린 학번만 반납할 수 있습니다."

        conn.commit()
        return redirect(f"/u/{num}")

    # GET 요청일 때 현재 상태 표시
    cur.execute("SELECT * FROM umbrellas WHERE id=?", (num,))
    umbrella = cur.fetchone()

    if umbrella["status"] == "available":
        status_text = f"{num}번 우산 🟢 사용 가능"
        button_text = "대여하기"
    else:
        status_text = f"{num}번 우산 🔴 대여 중 (학번: {umbrella['student_id']})"
        button_text = "반납하기"

    return f"""
        <h2>{status_text}</h2>
        <form method="POST">
            <input type="text" name="student_id" placeholder="학번 입력" required>
            <button type="submit">{button_text}</button>
        </form>
    """

if __name__ == "__main__":
    app.run(debug=True)