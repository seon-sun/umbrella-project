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

MAX_PER_STUDENT = 2  # 학생당 최대 대여 수

# ------------------
# 전체 우산 페이지 (대여자)
# ------------------
@app.route("/u/all", methods=["GET", "POST"])
def all_umbrellas():
    conn = get_db()
    cur = conn.cursor()

    student_id = request.form.get("student_id") or ""
    rent_id = request.form.get("rent_id")
    return_id = request.form.get("return_id")

    # 현재 학생 대여 수 계산
    if student_id:
        cur.execute("SELECT COUNT(*) as cnt FROM umbrellas WHERE student_id=?", (student_id,))
        current_count = cur.fetchone()["cnt"]
    else:
        current_count = 0

    # 대여 처리
    if rent_id and student_id:
        if current_count >= MAX_PER_STUDENT:
            pass  # 더 이상 대여 불가
        else:
            cur.execute("SELECT status FROM umbrellas WHERE id=?", (rent_id,))
            umbrella = cur.fetchone()
            if umbrella["status"] == "available":
                cur.execute(
                    "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                    (student_id, rent_id)
                )
                conn.commit()

    # 반납 처리 (본인만)
    elif return_id and student_id:
        cur.execute("SELECT student_id FROM umbrellas WHERE id=?", (return_id,))
        umbrella = cur.fetchone()
        if umbrella and umbrella["student_id"] == student_id:
            cur.execute(
                "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                (return_id,)
            )
            conn.commit()

    # 전체 우산 조회
    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    html = """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>전체 우산 대여</title>
        <style>
            body { font-family: sans-serif; margin:20px; }
            .umbrella { margin-bottom:15px; display:flex; align-items:center; flex-wrap:wrap; }
            .umbrella button { margin-left:10px; padding:5px 10px; flex-shrink:0; }
            input[name="student_id"] { padding:5px; width:100%; max-width:200px; margin-bottom:15px; }
        </style>
    </head>
    <body>
    <h1>전체 우산 대여 페이지</h1>
    <form method="POST">
        <input type="text" name="student_id" placeholder="학번 입력" required value="{{ student_id }}">
        {% for u in umbrellas %}
            <div class="umbrella">
                <strong>{{ u.id }}번 우산:</strong>
                {% if u.status == 'available' %}
                    🟢 사용 가능
                    {% if student_id and current_count < max_count %}
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
    return render_template_string(html, umbrellas=umbrellas, student_id=student_id,
                                  current_count=current_count, max_count=MAX_PER_STUDENT)

# ------------------
# 개별 우산 페이지
# ------------------
@app.route("/u/<int:num>", methods=["GET", "POST"])
def umbrella(num):
    conn = get_db()
    cur = conn.cursor()
    message = ""
    student_id = request.form.get("student_id") or ""

    # 현재 학생 대여 수
    current_count = 0
    if student_id:
        cur.execute("SELECT COUNT(*) as cnt FROM umbrellas WHERE student_id=?", (student_id,))
        current_count = cur.fetchone()["cnt"]

    if request.method == "POST":
        cur.execute("SELECT status, student_id FROM umbrellas WHERE id=?", (num,))
        umbrella = cur.fetchone()
        if not umbrella:
            return "잘못된 우산 번호입니다."
        if umbrella["status"] == "available":
            if current_count >= MAX_PER_STUDENT:
                message = f"최대 {MAX_PER_STUDENT}개까지 대여 가능합니다."
            else:
                cur.execute(
                    "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                    (student_id, num)
                )
                conn.commit()
        else:
            if umbrella["student_id"] == student_id:
                cur.execute(
                    "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                    (num,)
                )
                conn.commit()
            else:
                message = "이 우산을 빌린 학번만 반납할 수 있습니다."

        return redirect(f"/u/{num}")

    # GET 요청
    cur.execute("SELECT * FROM umbrellas WHERE id=?", (num,))
    umbrella = cur.fetchone()
    if not umbrella:
        return "해당 우산은 존재하지 않습니다."

    html = """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{{ umbrella.id }}번 우산</title>
        <style>
            body { font-family:sans-serif; margin:20px; }
            button { padding:5px 10px; margin-top:10px; }
            input[name="student_id"] { padding:5px; width:100%; max-width:200px; margin-top:10px; }
        </style>
    </head>
    <body>
        <h2>{{ umbrella.id }}번 우산 {% if umbrella.status=='available' %}🟢 사용 가능{% else %}🔴 대여 중{% endif %}</h2>
        {% if message %}
            <p style="color:red;">{{ message }}</p>
        {% endif %}
        <form method="POST">
            <input type="text" name="student_id" placeholder="학번 입력" required>
            {% if umbrella.status=='available' %}
                {% if student_id and current_count < max_count %}
                    <button type="submit">대여하기</button>
                {% endif %}
            {% else %}
                {% if umbrella.student_id == student_id %}
                    <button type="submit">반납하기</button>
                {% endif %}
            {% endif %}
        </form>
    </body>
    </html>
    """
    return render_template_string(html, umbrella=umbrella, message=message,
                                  student_id=student_id, current_count=current_count,
                                  max_count=MAX_PER_STUDENT)

# ------------------
# 관리자 페이지
# ------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_page():
    admin_pass = "0927"  # 원하는 비밀번호
    input_pass = request.args.get("pass")
    if input_pass != admin_pass:
        return "관리자 인증 필요. URL 뒤에 ?pass=비밀번호 를 붙여주세요."

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

    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    html = """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>관리자 페이지</title>
        <style>
            body { font-family:sans-serif; margin:20px; }
            .umbrella { margin-bottom:10px; display:flex; align-items:center; flex-wrap:wrap; }
            .umbrella button { margin-left:10px; padding:5px 10px; flex-shrink:0; }
        </style>
    </head>
    <body>
        <h1>관리자 페이지</h1>
        <form method="POST">
            {% for u in umbrellas %}
                <div class="umbrella">
                    <strong>{{ u.id }}번 우산</strong> - {{ u.status }} - 학번: {{ u.student_id }}
                    {% if u.status=='rented' %}
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
if __name__ == "__main__":
    app.run(debug=True)