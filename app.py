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
# 학생 대여 수 조회
# ------------------
def get_student_count(student_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM umbrellas WHERE student_id=?", (str(student_id),))
    result = cur.fetchone()
    return result["cnt"] if result else 0

# ------------------
# 전체 우산 대여 페이지
# ------------------
@app.route("/u/all", methods=["GET", "POST"])
def all_umbrellas():
    conn = get_db()
    cur = conn.cursor()
    student_id = request.form.get("student_id") or ""
    rent_id = request.form.get("rent_id")
    return_id = request.form.get("return_id")

    if request.method == "POST":
        # 대여 처리
        if rent_id and student_id:
            if get_student_count(student_id) < 2:
                cur.execute("SELECT status FROM umbrellas WHERE id=?", (rent_id,))
                umbrella = cur.fetchone()
                if umbrella and umbrella["status"] == "available":
                    cur.execute(
                        "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                        (str(student_id), rent_id)
                    )
                    conn.commit()

        # 반납 처리 (본인만)
        if return_id and student_id:
            cur.execute("SELECT student_id FROM umbrellas WHERE id=?", (return_id,))
            umbrella = cur.fetchone()
            if umbrella and umbrella["student_id"] == str(student_id):
                cur.execute(
                    "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                    (return_id,)
                )
                conn.commit()

        return redirect("/u/all")

    # 전체 우산 조회
    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()
    student_count = get_student_count(student_id) if student_id else 0

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>전체 우산 대여</title>
    </head>
    <body>
    <h1>전체 우산 대여 페이지</h1>
    <form method="POST">
        <input type="text" name="student_id" placeholder="학번 입력" required value="{{ student_id }}">
        <br><br>
        {% for u in umbrellas %}
            <div style="margin-bottom:10px;">
                <strong>{{ u.id }}번 우산:</strong>
                {% if u.status == 'available' %}
                    🟢 사용 가능
                    {% if student_id and student_count < 2 %}
                        <button type="submit" name="rent_id" value="{{ u.id }}">대여하기</button>
                    {% else %}
                        <button type="button" disabled>대여 불가</button>
                    {% endif %}
                {% else %}
                    🔴 대여 중
                    {% if u.student_id == student_id %}
                        <button type="submit" name="return_id" value="{{ u.id }}">반납하기</button>
                    {% else %}
                        <button type="button" disabled>대여 중</button>
                    {% endif %}
                {% endif %}
            </div>
        {% endfor %}
    </form>
    </body>
    </html>
    """
    return render_template_string(html, umbrellas=umbrellas, student_id=student_id, student_count=student_count)

# ------------------
# 개별 우산 페이지
# ------------------
@app.route("/u/<int:num>", methods=["GET", "POST"])
def umbrella(num):
    conn = get_db()
    cur = conn.cursor()
    student_id = request.form.get("student_id") or ""

    if request.method == "POST":
        cur.execute("SELECT status, student_id FROM umbrellas WHERE id=?", (num,))
        umbrella = cur.fetchone()

        # 대여
        if umbrella["status"] == "available" and get_student_count(student_id) < 2:
            cur.execute(
                "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                (str(student_id), num)
            )
            conn.commit()
        # 반납
        elif umbrella["student_id"] == str(student_id):
            cur.execute(
                "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                (num,)
            )
            conn.commit()

        return redirect(f"/u/{num}")

    # 조회
    cur.execute("SELECT * FROM umbrellas WHERE id=?", (num,))
    umbrella = cur.fetchone()
    can_rent = umbrella["status"] == "available" and (student_id and get_student_count(student_id) < 2)
    show_return = umbrella["status"] == "rented" and umbrella["student_id"] == str(student_id)

    status_text = f"{num}번 우산 🟢 사용 가능" if umbrella["status"] == "available" else f"{num}번 우산 🔴 대여 중"
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{{ num }}번 우산</title>
    </head>
    <body>
        <h2>{{ status_text }}</h2>
        <form method="POST">
            <input type="text" name="student_id" placeholder="학번 입력" required value="{{ student_id }}">
            {% if can_rent %}
                <button type="submit">대여하기</button>
            {% endif %}
            {% if show_return %}
                <button type="submit">반납하기</button>
            {% endif %}
        </form>
    </body>
    </html>
    """
    return render_template_string(html, num=num, status_text=status_text, umbrella=umbrella, student_id=student_id, can_rent=can_rent, show_return=show_return)

# ------------------
# 관리자 페이지
# ------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_page():
    admin_pass = "0927"
    input_pass = request.args.get("pass")
    if input_pass != admin_pass:
        return "관리자 인증 필요. URL 뒤에 ?pass=1234 를 붙여주세요."

    conn = get_db()
    cur = conn.cursor()

    force_return_id = request.form.get("force_return_id")
    if force_return_id:
        cur.execute(
            "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
            (force_return_id,)
        )
        conn.commit()
        return redirect(f"/admin?pass={admin_pass}")

    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>관리자 페이지</title>
    </head>
    <body>
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
    </body>
    </html>
    """
    return render_template_string(html, umbrellas=umbrellas)

# ------------------
if __name__ == "__main__":
    app.run(debug=True)