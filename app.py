from flask import Flask, request, redirect, render_template_string
import sqlite3

app = Flask(__name__)

# ------------------
# DB 연결
# ------------------
def get_db():
    conn = sqlite3.connect("umbrellas.db")
    conn.row_factory = sqlite3.Row
    return conn

# ------------------
# 전체 우산 페이지 (사용자용)
# ------------------
@app.route("/u/all", methods=["GET", "POST"])
def all_umbrellas():
    conn = get_db()
    cur = conn.cursor()

    student_id = request.form.get("student_id") or ""
    rent_id = request.form.get("rent_id")
    return_id = request.form.get("return_id")

    # 현재 학번 대여 개수 조회
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
                return f"이미 2개 대여 중입니다. 하나를 반납 후 대여해주세요."

    # 반납 처리 (본인만 가능)
    elif return_id and student_id:
        cur.execute("SELECT status, student_id FROM umbrellas WHERE id=?", (return_id,))
        umbrella = cur.fetchone()
        if umbrella["student_id"] == student_id:
            cur.execute(
                "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                (return_id,)
            )
            conn.commit()

    # 전체 우산 상태 조회
    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    # HTML 템플릿 (모바일 친화적)
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>전체 우산 대여</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 10px; }
            input, button { width: 100%; padding: 12px; font-size: 1.1em; margin-top: 5px; }
            .umbrella-card { border:1px solid #ccc; border-radius:8px; padding:10px; margin-bottom:10px; }
        </style>
    </head>
    <body>
        <h1>전체 우산 대여 페이지</h1>
        <form method="POST">
            <input type="text" name="student_id" placeholder="학번 입력" required value="{{ student_id }}">
            <br><br>
            {% for u in umbrellas %}
                <div class="umbrella-card">
                    <strong>{{ u.id }}번 우산:</strong>
                    {% if u.status == 'available' %}
                        🟢 사용 가능
                        {% if rented_count < 2 %}
                            <button type="submit" name="rent_id" value="{{ u.id }}">대여하기</button>
                        {% else %}
                            <span style="color:red;">대여 불가 (최대 2개)</span>
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
# 관리자 페이지
# ------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_page():
    admin_pass = "0927"  # 관리자 비밀번호
    input_pass = request.args.get("pass")
    if input_pass != admin_pass:
        return "관리자 인증 필요. URL 뒤에 ?pass=0927 를 붙여주세요."

    conn = get_db()
    cur = conn.cursor()

    # 강제 반납 처리
    force_return_id = request.form.get("force_return_id")
    if force_return_id:
        cur.execute(
            "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
            (force_return_id,)
        )
        conn.commit()

    # 전체 우산 조회
    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>관리자 페이지</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 10px; }
            button { padding:10px; font-size:1em; margin-top:5px; width:100%; }
            .umbrella-card { border:1px solid #ccc; border-radius:8px; padding:10px; margin-bottom:10px; }
        </style>
    </head>
    <body>
        <h1>관리자 페이지</h1>
        <form method="POST">
            {% for u in umbrellas %}
                <div class="umbrella-card">
                    <strong>{{ u.id }}번 우산</strong> - {{ u.status }} - 학번: {{ u.student_id }}
                    {% if u.status == 'rented' %}
                        <button type="submit" name="force_return_id" value="{{ u.id }}">강제 반납</button>
                    {% endif %}
                </div>
            {% endfor %}
        </form>
    </body>
    </html>
    """
    return render_template_string(html, umbrellas=umbrellas)

# ------------------
# 개별 우산 페이지 (선택 가능)
# ------------------
@app.route("/u/<int:num>", methods=["GET", "POST"])
def umbrella(num):
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        student_id = request.form.get("student_id")
        cur.execute("SELECT status, student_id FROM umbrellas WHERE id=?", (num,))
        umbrella = cur.fetchone()

        # 현재 학번 대여 개수
        cur.execute("SELECT COUNT(*) as cnt FROM umbrellas WHERE student_id=? AND status='rented'", (student_id,))
        rented_count = cur.fetchone()["cnt"]

        if umbrella["status"] == "available":
            if rented_count < 2:
                cur.execute(
                    "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                    (student_id, num)
                )
            else:
                return f"이미 2개 대여 중입니다. 하나를 반납 후 대여해주세요."
        else:
            if umbrella["student_id"] == student_id:
                cur.execute(
                    "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                    (num,)
                )
            else:
                return "이 우산을 빌린 학번만 반납할 수 있습니다."

        conn.commit()
        return redirect(f"/u/{num}")

    cur.execute("SELECT * FROM umbrellas WHERE id=?", (num,))
    umbrella = cur.fetchone()

    status_text = f"{num}번 우산 🟢 사용 가능" if umbrella["status"] == "available" else f"{num}번 우산 🔴 대여 중"
    button_text = "대여하기" if umbrella["status"] == "available" else "반납하기"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{num}번 우산</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 10px; }}
            input, button {{ width: 100%; padding: 12px; font-size: 1.2em; margin-top: 5px; }}
        </style>
    </head>
    <body>
        <h2>{status_text}</h2>
        <form method="POST">
            <input type="text" name="student_id" placeholder="학번 입력" required>
            <button type="submit">{button_text}</button>
        </form>
    </body>
    </html>
    """
    return html

# ------------------
if __name__ == "__main__":
    app.run(debug=True)