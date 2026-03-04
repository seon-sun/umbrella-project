from flask import Flask, request, redirect, render_template_string
import sqlite3
import re

app = Flask(__name__)

# ------------------
# DB 연결
# ------------------
def get_db():
    conn = sqlite3.connect("umbrellas.db")
    conn.row_factory = sqlite3.Row
    return conn

# ------------------
# 학번 유효성 검사
# ------------------
def valid_student_id(student_id):
    pattern = r"^\d{4}/304/\d{3}$"
    return re.match(pattern, student_id) is not None

# ------------------
# 전체 우산 페이지
# ------------------
@app.route("/u/all", methods=["GET", "POST"])
def all_umbrellas():
    conn = get_db()
    cur = conn.cursor()

    student_id = request.form.get("student_id") or ""
    rent_id = request.form.get("rent_id")
    return_id = request.form.get("return_id")
    message = ""

    # 대여 처리
    if rent_id and valid_student_id(student_id):
        # 현재 학번 대여 중인 우산 수
        cur.execute("SELECT COUNT(*) as cnt FROM umbrellas WHERE student_id=?", (student_id,))
        count = cur.fetchone()["cnt"]

        if count >= 2:
            message = "최대 2개까지만 대여 가능합니다."
        else:
            cur.execute("SELECT status FROM umbrellas WHERE id=?", (rent_id,))
            umbrella = cur.fetchone()
            if umbrella["status"] == "available":
                cur.execute(
                    "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                    (student_id, rent_id)
                )
                conn.commit()
                message = f"{rent_id}번 우산 대여 완료"

    # 반납 처리
    elif return_id and valid_student_id(student_id):
        cur.execute("SELECT status, student_id FROM umbrellas WHERE id=?", (return_id,))
        umbrella = cur.fetchone()
        if umbrella["student_id"] == student_id:
            cur.execute(
                "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                (return_id,)
            )
            conn.commit()
            message = f"{return_id}번 우산 반납 완료"

    # 전체 우산 조회
    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    # HTML + JS 템플릿
    html = """
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <h1>전체 우산 대여 페이지</h1>
    <p style="color:red;">{{ message }}</p>
    <form method="POST" id="umbrellaForm">
        <input type="text" name="student_id" id="student_id" placeholder="학번 입력 (YYYY/304/XXX)" required value="{{ student_id }}">
        <br><br>
        {% for u in umbrellas %}
            <div style="margin-bottom:10px;">
                <strong>{{ u.id }}번 우산:</strong>
                {% if u.status == 'available' %}
                    🟢 사용 가능
                    <button type="submit" name="rent_id" value="{{ u.id }}" class="rent-btn">대여하기</button>
                {% else %}
                    🔴 대여 중
                    {% if u.student_id == student_id %}
                        <button type="submit" name="return_id" value="{{ u.id }}" class="return-btn">반납하기</button>
                    {% endif %}
                {% endif %}
            </div>
        {% endfor %}
    </form>

    <script>
        const studentInput = document.getElementById('student_id');
        const rentButtons = document.querySelectorAll('.rent-btn');
        const returnButtons = document.querySelectorAll('.return-btn');

        function validate() {
            const val = studentInput.value;
            const pattern = /^\\d{4}\/304\/\\d{3}$/;
            const valid = pattern.test(val);

            rentButtons.forEach(btn => btn.disabled = !valid);
            returnButtons.forEach(btn => btn.disabled = !valid);
        }

        studentInput.addEventListener('input', validate);
        window.addEventListener('load', validate);
    </script>
    """
    return render_template_string(html, umbrellas=umbrellas, student_id=student_id, message=message)

# ------------------
# 개별 우산 페이지
# ------------------
@app.route("/u/<int:num>", methods=["GET", "POST"])
def umbrella(num):
    conn = get_db()
    cur = conn.cursor()
    message = ""

    if request.method == "POST":
        student_id = request.form.get("student_id")
        if not valid_student_id(student_id):
            message = "학번 형식이 잘못되었습니다."
        else:
            cur.execute("SELECT status, student_id FROM umbrellas WHERE id=?", (num,))
            umbrella = cur.fetchone()
            if umbrella["status"] == "available":
                cur.execute(
                    "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                    (student_id, num)
                )
                conn.commit()
                message = f"{num}번 우산 대여 완료"
            elif umbrella["student_id"] == student_id:
                cur.execute(
                    "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                    (num,)
                )
                conn.commit()
                message = f"{num}번 우산 반납 완료"
            else:
                message = "다른 학번이 대여 중입니다."

        return redirect(f"/u/{num}")

    cur.execute("SELECT * FROM umbrellas WHERE id=?", (num,))
    umbrella = cur.fetchone()

    status_text = f"{num}번 우산 {'🟢 사용 가능' if umbrella['status']=='available' else '🔴 대여 중'}"
    button_text = "대여하기" if umbrella['status']=='available' else "반납하기"

    html = """
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <h2>{{ status_text }}</h2>
    <p style="color:red;">{{ message }}</p>
    <form method="POST">
        <input type="text" name="student_id" id="student_id" placeholder="학번 입력 (YYYY/304/XXX)" required>
        <button type="submit" id="action-btn">{{ button_text }}</button>
    </form>
    <script>
        const input = document.getElementById('student_id');
        const btn = document.getElementById('action-btn');
        const pattern = /^\\d{4}\/304\/\\d{3}$/;
        function validate() {
            btn.disabled = !pattern.test(input.value);
        }
        input.addEventListener('input', validate);
        window.addEventListener('load', validate);
    </script>
    """
    return render_template_string(html, status_text=status_text, button_text=button_text, message=message)

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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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