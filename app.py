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
# 학번 검증
# ------------------
def validate_student_id(student_id):
    return student_id.isdigit() and len(student_id) == 10

# ------------------
# 사용자 전체 페이지 (대여자)
# ------------------
@app.route("/u/all", methods=["GET", "POST"])
def all_umbrellas():
    conn = get_db()
    cur = conn.cursor()

    student_id = request.form.get("student_id", "")
    rent_id = request.form.get("rent_id")
    return_id = request.form.get("return_id")

    # 현재 학번이 이미 몇 개 빌렸는지 확인
    rented_count = 0
    if validate_student_id(student_id):
        cur.execute("SELECT COUNT(*) AS cnt FROM umbrellas WHERE student_id=?", (student_id,))
        rented_count = cur.fetchone()["cnt"]

    # 대여 처리
    if rent_id and validate_student_id(student_id):
        cur.execute("SELECT status FROM umbrellas WHERE id=?", (rent_id,))
        umbrella = cur.fetchone()
        if umbrella["status"] == "available" and rented_count < 2:
            cur.execute(
                "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                (student_id, rent_id)
            )
            conn.commit()
            return redirect("/u/all")

    # 반납 처리
    if return_id and validate_student_id(student_id):
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <h1>전체 우산 대여 페이지</h1>
    <form method="POST">
        <input type="text" name="student_id" placeholder="학번 10자리 입력" value="{{ student_id }}" required>
        <br><br>
        {% for u in umbrellas %}
            <div style="margin-bottom:10px;">
                <strong>{{ u.id }}번 우산:</strong>
                {% if u.status == 'available' %}
                    🟢 사용 가능
                    {% if validate_student_id(student_id) and rented_count < 2 %}
                        <button type="submit" name="rent_id" value="{{ u.id }}">대여하기</button>
                    {% else %}
                        <button disabled>대여 불가</button>
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
    """
    return render_template_string(html, umbrellas=umbrellas, student_id=student_id,
                                  rented_count=rented_count, validate_student_id=validate_student_id)

# ------------------
# 개별 우산 페이지
# ------------------
@app.route("/u/<int:num>", methods=["GET", "POST"])
def umbrella(num):
    conn = get_db()
    cur = conn.cursor()
    student_id = request.form.get("student_id", "")

    # 대여 처리
    if request.method == "POST" and validate_student_id(student_id):
        cur.execute("SELECT status, student_id FROM umbrellas WHERE id=?", (num,))
        umbrella = cur.fetchone()
        if umbrella["status"] == "available":
            # 학번이 2개 이상 빌렸는지 체크
            cur.execute("SELECT COUNT(*) AS cnt FROM umbrellas WHERE student_id=?", (student_id,))
            rented_count = cur.fetchone()["cnt"]
            if rented_count < 2:
                cur.execute(
                    "UPDATE umbrellas SET status='rented', student_id=? WHERE id=?",
                    (student_id, num)
                )
                conn.commit()
                return redirect(f"/u/{num}")
        elif umbrella["student_id"] == student_id:
            cur.execute(
                "UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?",
                (num,)
            )
            conn.commit()
            return redirect(f"/u/{num}")

    # 현재 우산 상태
    cur.execute("SELECT * FROM umbrellas WHERE id=?", (num,))
    umbrella = cur.fetchone()

    html = """
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <h2>{{ num }}번 우산 {% if umbrella.status == 'available' %}🟢 사용 가능{% else %}🔴 대여 중{% endif %}</h2>
    <form method="POST">
        <input type="text" name="student_id" placeholder="학번 10자리 입력" value="{{ student_id }}" required>
        {% if umbrella.status == 'available' %}
            <button type="submit">대여하기</button>
        {% elif umbrella.student_id == student_id %}
            <button type="submit">반납하기</button>
        {% endif %}
    </form>
    """
    return render_template_string(html, umbrella=umbrella, num=num, student_id=student_id)

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