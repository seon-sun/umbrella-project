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
# 전체 페이지 (대여자)
# ------------------
@app.route("/u/all", methods=["GET", "POST"])
def all_umbrellas():
    conn = get_db()
    cur = conn.cursor()

    student_id = request.form.get("student_id") or ""
    rent_id = request.form.get("rent_id")
    return_id = request.form.get("return_id")

    # 현재 학생이 빌린 우산 수
    cur.execute("SELECT COUNT(*) FROM umbrellas WHERE student_id=?", (student_id,))
    rented_count = cur.fetchone()[0]

    # 대여 처리
    if rent_id and student_id:
        if rented_count < 2:
            cur.execute("SELECT status FROM umbrellas WHERE id=?", (rent_id,))
            umbrella = cur.fetchone()
            if umbrella["status"] == "available":
                cur.execute(
                    "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                    (student_id, rent_id)
                )
                conn.commit()
        return redirect("/u/all")

    # 반납 처리
    if return_id and student_id:
        cur.execute("SELECT student_id FROM umbrellas WHERE id=?", (return_id,))
        umbrella = cur.fetchone()
        if umbrella["student_id"] == student_id:
            cur.execute(
                "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                (return_id,)
            )
            conn.commit()
        return redirect("/u/all")

    # 전체 우산 상태 조회
    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    html = """
    <!DOCTYPE html>
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>전체 우산 대여 페이지</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 10px; }
        .umbrella { margin-bottom: 10px; }
        button:disabled { opacity: 0.5; }
    </style>
    </head>
    <body>
    <h1>전체 우산 대여 페이지</h1>
    <form method="POST" id="umbrella_form">
        <input type="text" id="student_id" name="student_id" placeholder="학번 입력 (10자리)" required value="{{ student_id }}">
        <br><br>
        {% for u in umbrellas %}
            <div class="umbrella">
                <strong>{{ u.id }}번 우산:</strong>
                {% if u.status == 'available' %}
                    🟢 사용 가능
                    <button type="submit" name="rent_id" value="{{ u.id }}" class="rent_button">대여하기</button>
                {% else %}
                    🔴 대여 중
                    {% if u.student_id == student_id %}
                        <button type="submit" name="return_id" value="{{ u.id }}" class="return_button">반납하기</button>
                    {% endif %}
                {% endif %}
            </div>
        {% endfor %}
    </form>

    <script>
    const studentInput = document.getElementById("student_id");
    const rentButtons = document.querySelectorAll(".rent_button");
    const returnButtons = document.querySelectorAll(".return_button");

    function updateButtons() {
        const value = studentInput.value;
        const valid = value.length === 10 && /^\\d{10}$/.test(value);

        rentButtons.forEach(btn => btn.disabled = !valid);
        returnButtons.forEach(btn => btn.disabled = !valid);
    }

    studentInput.addEventListener("input", updateButtons);
    window.addEventListener("load", updateButtons);
    </script>
    </body>
    </html>
    """
    return render_template_string(html, umbrellas=umbrellas, student_id=student_id)

# ------------------
# 개별 우산 페이지
# ------------------
@app.route("/u/<int:num>", methods=["GET", "POST"])
def umbrella(num):
    conn = get_db()
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
            conn.commit()
        elif umbrella["student_id"] == student_id:
            cur.execute(
                "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                (num,)
            )
            conn.commit()
        return redirect(f"/u/{num}")

    cur.execute("SELECT * FROM umbrellas WHERE id=?", (num,))
    umbrella = cur.fetchone()
    student_id = ""

    html = """
    <!DOCTYPE html>
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ umbrella.id }}번 우산</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 10px; }
        button:disabled { opacity: 0.5; }
    </style>
    </head>
    <body>
    <h2>{{ umbrella.id }}번 우산 상태: {{ '🟢 사용 가능' if umbrella.status=='available' else '🔴 대여 중' }}</h2>
    <form method="POST" id="umbrella_form">
        <input type="text" id="student_id" name="student_id" placeholder="학번 입력 (10자리)" required>
        <br><br>
        {% if umbrella.status == 'available' %}
            <button type="submit" class="rent_button">대여하기</button>
        {% elif umbrella.student_id %}
            <button type="submit" class="return_button">반납하기</button>
        {% endif %}
    </form>
    <script>
    const studentInput = document.getElementById("student_id");
    const rentButton = document.querySelector(".rent_button");
    const returnButton = document.querySelector(".return_button");

    function updateButtons() {
        const value = studentInput.value;
        const valid = value.length === 10 && /^\\d{10}$/.test(value);
        if(rentButton) rentButton.disabled = !valid;
        if(returnButton) returnButton.disabled = !valid;
    }

    studentInput.addEventListener("input", updateButtons);
    window.addEventListener("load", updateButtons);
    </script>
    </body>
    </html>
    """
    return render_template_string(html, umbrella=umbrella)

# ------------------
# 관리자 페이지
# ------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_page():
    admin_pass = "0927"
    input_pass = request.args.get("pass")
    if input_pass != admin_pass:
        return "관리자 인증 필요. URL 뒤에 ?pass=비밀번호 를 붙여주세요."

    conn = get_db()
    cur = conn.cursor()

    force_return_id = request.form.get("force_return_id")
    if force_return_id:
        cur.execute(
            "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
            (force_return_id,)
        )
        conn.commit()
        return redirect("/admin?pass=" + admin_pass)

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
        button { margin-left: 10px; }
    </style>
    </head>
    <body>
    <h1>관리자 페이지</h1>
    <form method="POST">
        {% for u in umbrellas %}
            <div>
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