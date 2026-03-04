from flask import Flask, request, redirect, url_for, render_template_string
import sqlite3

app = Flask(__name__)

DB_FILE = "umbrellas.db"

# ------------------
# DB 연결
# ------------------
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# ------------------
# 사용자 페이지 (모바일/웹 전체 페이지)
# ------------------
@app.route("/u/all", methods=["GET", "POST"])
def all_umbrellas():
    student_id = request.form.get("student_id") or ""
    rent_id = request.form.get("rent_id")
    return_id = request.form.get("return_id")

    with get_db() as conn:
        cur = conn.cursor()

        # 현재 학생이 빌린 우산 개수 확인
        cur.execute("SELECT COUNT(*) as cnt FROM umbrellas WHERE student_id=? AND status='rented'", (student_id,))
        rented_count = cur.fetchone()["cnt"]

        # 대여 처리
        if rent_id and student_id:
            cur.execute("SELECT status FROM umbrellas WHERE id=?", (rent_id,))
            umbrella = cur.fetchone()
            if umbrella["status"] == "available":
                if rented_count < 2:
                    cur.execute(
                        "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                        (student_id, rent_id)
                    )
                    conn.commit()
                else:
                    return f"학번 {student_id}는 최대 2개까지 대여 가능합니다.", 400
            return redirect(url_for("all_umbrellas"))

        # 반납 처리 (본인만)
        elif return_id and student_id:
            cur.execute("SELECT student_id FROM umbrellas WHERE id=?", (return_id,))
            umbrella = cur.fetchone()
            if umbrella["student_id"] == student_id:
                cur.execute(
                    "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                    (return_id,)
                )
                conn.commit()
            return redirect(url_for("all_umbrellas"))

        # 전체 우산 상태 조회
        cur.execute("SELECT * FROM umbrellas ORDER BY id")
        umbrellas = cur.fetchall()

    html = """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>우산 대여 페이지</title>
        <style>
            body { font-family: sans-serif; max-width: 600px; margin: auto; padding: 10px; }
            input, button { font-size: 1em; padding: 5px; margin: 3px 0; }
            div.umbrella { margin-bottom: 12px; }
        </style>
    </head>
    <body>
        <h1>전체 우산 대여 페이지</h1>
        <form method="POST">
            <input type="text" name="student_id" placeholder="학번 입력" required value="{{ student_id }}">
            <br><br>
            {% for u in umbrellas %}
                <div class="umbrella">
                    <strong>{{ u.id }}번 우산:</strong>
                    {% if u.status == 'available' %}
                        🟢 사용 가능
                        {% if student_id and rented_count < 2 %}
                            <button type="submit" name="rent_id" value="{{ u.id }}">대여하기</button>
                        {% endif %}
                    {% else %}
                        🔴 대여 중
                        {% if u.student_id == student_id %}
                            <button type="submit" name="return_id" value="{{ u.id }}">반납하기</button>
                        {% endif %}
                    {% endif %}
                </div>
            {% endfor %}
        </form>
    </body>
    </html>
    """
    return render_template_string(html, umbrellas=umbrellas, student_id=student_id, rented_count=rented_count)

# ------------------
# 개별 우산 페이지 (선택)
# ------------------
@app.route("/u/<int:num>", methods=["GET", "POST"])
def umbrella(num):
    with get_db() as conn:
        cur = conn.cursor()

        if request.method == "POST":
            student_id = request.form.get("student_id")
            cur.execute("SELECT status, student_id FROM umbrellas WHERE id=?", (num,))
            umbrella = cur.fetchone()

            if umbrella["status"] == "available":
                cur.execute(
                    "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                    (student_id, num)
                )
            else:
                if umbrella["student_id"] == student_id:
                    cur.execute(
                        "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                        (num,)
                    )
                else:
                    return "이 우산을 빌린 학번만 반납할 수 있습니다.", 400

            conn.commit()
            return redirect(url_for("umbrella", num=num))

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

# ------------------
# 관리자 페이지
# ------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_page():
    admin_pass = "1234"
    input_pass = request.args.get("pass")
    if input_pass != admin_pass:
        return "관리자 인증 필요. URL 뒤에 ?pass=비밀번호 를 붙여주세요."

    with get_db() as conn:
        cur = conn.cursor()

        # 강제 반납
        force_return_id = request.form.get("force_return_id")
        if force_return_id:
            cur.execute(
                "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                (force_return_id,)
            )
            conn.commit()

        cur.execute("SELECT * FROM umbrellas ORDER BY id")
        umbrellas = cur.fetchall()

    html = """
    <h1>관리자 페이지</h1>
    <form method="POST">
        {% for u in umbrellas %}
            <div style="margin-bottom:10px;">
                <strong>{{ u.id }}번 우산</strong> - {{ u.status }} - 학번: {{ u.student_id }}
                {% if u.status == 'rented' %}
                    <button type="submit" name="force_return_id" value="{{ u.id }}">강제 반납</button>
                {% endif %}
            </div>
        {% endfor %}
    </form>
    """
    return render_template_string(html, umbrellas=umbrellas)

# ------------------
if __name__ == "__main__":
    app.run(debug=True)