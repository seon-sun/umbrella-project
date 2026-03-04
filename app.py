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
# 사용자 페이지 (전체)
# ------------------
@app.route("/u/all", methods=["GET", "POST"])
def all_umbrellas():
    conn = get_db()
    cur = conn.cursor()

    student_id = request.form.get("student_id") or ""
    rent_id = request.form.get("rent_id")
    return_id = request.form.get("return_id")

    # 현재 학생이 빌린 개수
    cur.execute("SELECT COUNT(*) as cnt FROM umbrellas WHERE student_id=?", (student_id,))
    rented_count = cur.fetchone()["cnt"]

    # 대여 처리
    if rent_id and student_id:
        cur.execute("SELECT status FROM umbrellas WHERE id=?", (rent_id,))
        umbrella = cur.fetchone()
        if umbrella["status"] == "available" and rented_count < 2:
            cur.execute(
                "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                (student_id, rent_id)
            )
            conn.commit()
            rented_count += 1

    # 반납 처리
    elif return_id and student_id:
        cur.execute("SELECT status, student_id FROM umbrellas WHERE id=?", (return_id,))
        umbrella = cur.fetchone()
        if umbrella["student_id"] == student_id:
            cur.execute(
                "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                (return_id,)
            )
            conn.commit()
            rented_count -= 1

    # 전체 우산 조회
    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    # ------------------
    # HTML + JS
    # ------------------
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
        const student = studentInput.value;
        const valid = student.length === 10 && /^\\d{10}$/.test(student);

        // 현재 학생이 빌린 개수 (서버에서 렌더링된 값)
        let rentedCount = {{ rented_count }};

        // 대여 버튼
        rentButtons.forEach(btn => {
            if (!valid) {
                btn.disabled = true;
                btn.textContent = "학번 입력 필요";
            } else if (rentedCount >= 2) {
                btn.disabled = true;
                btn.textContent = "대여 불가 (2개 제한)";
            } else {
                btn.disabled = false;
                btn.textContent = "대여하기";
            }
        });

        // 반납 버튼
        returnButtons.forEach(btn => {
            btn.disabled = !valid; // 학번 10자리일 때만 활성화
        });
    }

    studentInput.addEventListener("input", updateButtons);
    window.addEventListener("load", updateButtons);
    </script>
    </body>
    </html>
    """
    return render_template_string(html, umbrellas=umbrellas, student_id=student_id, rented_count=rented_count)


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
# 개별 우산 페이지
# ------------------
@app.route("/u/<int:num>", methods=["GET", "POST"])
def umbrella(num):
    conn = get_db()
    cur = conn.cursor()
    student_id = ""

    if request.method == "POST":
        student_id = request.form.get("student_id")
        cur.execute("SELECT status, student_id FROM umbrellas WHERE id=?", (num,))
        umbrella = cur.fetchone()

        # 대여
        if umbrella["status"] == "available":
            cur.execute(
                "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                (student_id, num)
            )
        # 반납
        elif umbrella["student_id"] == student_id:
            cur.execute(
                "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                (num,)
            )
        conn.commit()
        return redirect(f"/u/{num}")

    cur.execute("SELECT * FROM umbrellas WHERE id=?", (num,))
    umbrella = cur.fetchone()

    if umbrella["status"] == "available":
        status_text = f"{num}번 우산 🟢 사용 가능"
        button_text = "대여하기"
        disable_return = True
    else:
        status_text = f"{num}번 우산 🔴 대여 중"
        button_text = "반납하기"
        disable_return = False if umbrella["student_id"] else True

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{num}번 우산</title>
    </head>
    <body>
        <h2>{status_text}</h2>
        <form method="POST">
            <input type="text" name="student_id" placeholder="학번 입력 (10자리)" value="{student_id}" required>
            <button type="submit" {'disabled' if disable_return else ''}>{button_text}</button>
        </form>
    </body>
    </html>
    """
    return html


# ------------------
if __name__ == "__main__":
    app.run(debug=True)