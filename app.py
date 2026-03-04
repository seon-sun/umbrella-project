from flask import Flask, request, redirect, render_template_string, jsonify
import sqlite3
import re

app = Flask(__name__)

# ------------------
# DB 연결
# ------------------
def get_db():
    conn = sqlite3.connect("umbrellas.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ------------------
# 유틸: 학번 검증
# ------------------
def valid_student_id(sid):
    return bool(re.fullmatch(r"\d{4}/304/\d{3}", sid))

# ------------------
# 사용자 페이지 (대여자)
# ------------------
@app.route("/u/all", methods=["GET", "POST"])
def all_umbrellas():
    conn = get_db()
    cur = conn.cursor()
    message = ""
    student_id = request.form.get("student_id") or ""
    rent_id = request.form.get("rent_id")
    return_id = request.form.get("return_id")

    # 학번 유효성 검사
    if student_id and not valid_student_id(student_id):
        message = "학번 형식이 올바르지 않습니다. YYYY/304/XXX 형태로 입력하세요."

    # 현재 학번 대여 수
    cur.execute("SELECT COUNT(*) as cnt FROM umbrellas WHERE student_id=?", (student_id,))
    rented_count = cur.fetchone()["cnt"]

    # 대여 처리
    if rent_id and valid_student_id(student_id):
        cur.execute("SELECT status FROM umbrellas WHERE id=?", (rent_id,))
        umbrella = cur.fetchone()
        if umbrella["status"] == "available":
            if rented_count >= 2:
                message = "이미 2개를 대여하였습니다. 더 이상 대여 불가."
            else:
                cur.execute(
                    "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                    (student_id, rent_id)
                )
                conn.commit()
                message = f"{rent_id}번 우산 대여 완료"
        else:
            message = "이미 대여 중인 우산입니다."

    # 반납 처리 (본인만 가능)
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
        else:
            message = "본인이 대여한 우산만 반납 가능합니다."

    # 전체 우산 상태 조회
    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    # HTML 템플릿 (모바일/웹 대응)
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
                    {% if student_id and student_id|length == 10 %}
                        {% if rented_count >= 2 %}
                            <button type="submit" name="rent_id" value="{{ u.id }}" disabled>대여불가 (2개 초과)</button>
                        {% else %}
                            <button type="submit" name="rent_id" value="{{ u.id }}">대여하기</button>
                        {% endif %}
                    {% else %}
                        <button type="submit" name="rent_id" value="{{ u.id }}" disabled>학번 확인 필요</button>
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

    <script>
    const studentInput = document.getElementById("student_id");
    const form = document.getElementById("umbrellaForm");
    studentInput.addEventListener("input", () => {
        form.submit();
    });
    </script>
    """
    return render_template_string(html, umbrellas=umbrellas, student_id=student_id, message=message, rented_count=rented_count)

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
            message = "학번 형식이 올바르지 않습니다."
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
                message = "이 우산을 빌린 학번만 반납할 수 있습니다."

    cur.execute("SELECT * FROM umbrellas WHERE id=?", (num,))
    umbrella = cur.fetchone()

    html = """
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <h2>{{ umbrella.id }}번 우산 상태: {{ umbrella.status }}{% if umbrella.status=='rented' %} (학번: {{ umbrella.student_id }}){% endif %}</h2>
    <p style="color:red;">{{ message }}</p>
    <form method="POST">
        <input type="text" name="student_id" placeholder="학번 입력 (YYYY/304/XXX)" required>
        {% if umbrella.status=='available' or umbrella.student_id==request.form.get('student_id') %}
            <button type="submit">
                {% if umbrella.status=='available' %}대여하기{% else %}반납하기{% endif %}
            </button>
        {% endif %}
    </form>
    """
    return render_template_string(html, umbrella=umbrella, message=message)

# ------------------
if __name__ == "__main__":
    app.run(debug=True)