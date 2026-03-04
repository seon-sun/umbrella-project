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
# 사용자 전체 페이지
# ------------------
@app.route("/u/all", methods=["GET", "POST"])
def all_umbrellas():
    conn = get_db()
    cur = conn.cursor()

    student_id = request.form.get("student_id") or ""
    rent_id = request.form.get("rent_id")
    return_id = request.form.get("return_id")

    # 현재 학생 대여 수 실시간 조회
    current_count = 0
    if student_id:
        cur.execute("SELECT COUNT(*) as cnt FROM umbrellas WHERE student_id=? AND status='rented'", (student_id,))
        current_count = cur.fetchone()["cnt"]

    # 대여 처리 (최대 2개)
    if rent_id and student_id:
        cur.execute("SELECT status FROM umbrellas WHERE id=?", (rent_id,))
        umbrella = cur.fetchone()
        if umbrella["status"] == "available":
            if current_count < 2:
                cur.execute("UPDATE umbrellas SET status='rented', student_id=? WHERE id=?", (student_id, rent_id))
                conn.commit()
                return redirect("/u/all")
            else:
                return f"학번 {student_id}는 이미 2개를 대여 중입니다."
        else:
            return "이미 대여 중인 우산입니다."

    # 반납 처리 (본인만 가능)
    if return_id and student_id:
        cur.execute("SELECT status, student_id FROM umbrellas WHERE id=?", (return_id,))
        umbrella = cur.fetchone()
        if umbrella["student_id"] == student_id:
            cur.execute("UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?", (return_id,))
            conn.commit()
            return redirect("/u/all")
        else:
            return "본인 학번만 반납 가능합니다."

    # 전체 우산 상태 조회
    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    # HTML 템플릿 (모바일/웹 반응형)
    html = """
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <h1>전체 우산 대여 페이지</h1>
    <form method="POST">
        <input type="text" name="student_id" placeholder="학번 입력" required value="{{ student_id }}">
        <br><br>
        {% for u in umbrellas %}
            <div style="margin-bottom:10px; border-bottom:1px solid #ccc; padding-bottom:5px;">
                <strong>{{ u.id }}번 우산:</strong>
                {% if u.status == 'available' %}
                    🟢 사용 가능
                    {% if current_count < 2 %}
                        <button type="submit" name="rent_id" value="{{ u.id }}">대여하기</button>
                    {% else %}
                        <button type="button" disabled>최대 2개 대여 불가</button>
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
    return render_template_string(html, umbrellas=umbrellas, student_id=student_id, current_count=current_count)

# ------------------
# 개별 우산 페이지 (모바일 대응)
# ------------------
@app.route("/u/<int:num>", methods=["GET", "POST"])
def umbrella(num):
    conn = get_db()
    cur = conn.cursor()

    student_id = request.form.get("student_id") or ""

    # 현재 학생 대여 수
    current_count = 0
    if student_id:
        cur.execute("SELECT COUNT(*) as cnt FROM umbrellas WHERE student_id=? AND status='rented'", (student_id,))
        current_count = cur.fetchone()["cnt"]

    if request.method == "POST":
        cur.execute("SELECT status, student_id FROM umbrellas WHERE id=?", (num,))
        umbrella = cur.fetchone()

        if umbrella["status"] == "available":
            if current_count < 2:
                cur.execute("UPDATE umbrellas SET status='rented', student_id=? WHERE id=?", (student_id, num))
                conn.commit()
                return redirect(f"/u/{num}")
            else:
                return f"학번 {student_id}는 이미 2개를 대여 중입니다."
        else:
            if umbrella["student_id"] == student_id:
                cur.execute("UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?", (num,))
                conn.commit()
                return redirect(f"/u/{num}")
            else:
                return "본인 학번만 반납 가능합니다."

    cur.execute("SELECT * FROM umbrellas WHERE id=?", (num,))
    umbrella = cur.fetchone()

    status_text = f"{num}번 우산 🟢 사용 가능" if umbrella["status"] == "available" else f"{num}번 우산 🔴 대여 중"
    button_text = "대여하기" if umbrella["status"] == "available" else "반납하기"

    html = f"""
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <h2>{status_text}</h2>
    <form method="POST">
        <input type="text" name="student_id" placeholder="학번 입력" required value="{student_id}">
        <button type="submit">{button_text}</button>
    </form>
    """
    return html

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

    # 강제 반납 처리
    force_return_id = request.form.get("force_return_id")
    if force_return_id:
        cur.execute("UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?", (force_return_id,))
        conn.commit()

    # 모든 우산 조회
    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    html = """
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <h1>관리자 페이지</h1>
    <form method="POST">
        {% for u in umbrellas %}
            <div style="margin-bottom:10px; border-bottom:1px solid #ccc; padding-bottom:5px;">
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