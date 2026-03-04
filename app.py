from flask import Flask, request, redirect, render_template_string
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
# 학번 유효성
# ------------------
def valid_student_id(sid):
    return bool(re.fullmatch(r"\d{4}304\d{3}", sid))  # YYYY304XXX 형태

# ------------------
# 전체 우산 페이지
# ------------------
@app.route("/u/all", methods=["GET", "POST"])
def all_umbrellas():
    conn = get_db()
    cur = conn.cursor()
    message = ""
    student_id = request.form.get("student_id") or ""
    rent_id = request.form.get("rent_id")
    return_id = request.form.get("return_id")

    # 현재 학번 대여 수
    cur.execute("SELECT COUNT(*) as cnt FROM umbrellas WHERE student_id=?", (student_id,))
    rented_count = cur.fetchone()["cnt"] if valid_student_id(student_id) else 0

    # 대여 처리
    if rent_id and valid_student_id(student_id):
        cur.execute("SELECT status FROM umbrellas WHERE id=?", (rent_id,))
        umbrella = cur.fetchone()
        if umbrella["status"] == "available":
            if rented_count >= 2:
                message = "더 이상 대여 불가 (2개 제한)"
            else:
                cur.execute("UPDATE umbrellas SET status='rented', student_id=? WHERE id=?", (student_id, rent_id))
                conn.commit()
                message = f"{rent_id}번 우산 대여 완료"
        else:
            message = "이미 대여 중인 우산입니다."

    # 반납 처리
    elif return_id and valid_student_id(student_id):
        cur.execute("SELECT status, student_id FROM umbrellas WHERE id=?", (return_id,))
        umbrella = cur.fetchone()
        if umbrella["student_id"] == student_id:
            cur.execute("UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?", (return_id,))
            conn.commit()
            message = f"{return_id}번 우산 반납 완료"
        else:
            message = "본인이 대여한 우산만 반납 가능합니다."

    # 전체 우산 조회
    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    html_all = """
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <!-- 모바일 즉시 대응 JS -->
    <script>
    (function(){
        if (/Mobi|Android/i.test(navigator.userAgent)) {
            document.body.classList.add('mobile');
            document.body.style.display='none';
            document.body.offsetHeight;
            document.body.style.display='';
        }
    })();
    </script>

    <!-- 모바일 대응 CSS -->
    <style>
    body { font-family: Arial, sans-serif; }
    .container { max-width: 1200px; margin: auto; }

    @media (max-width: 768px) {
        body { font-size: 16px; }
        .container { width: 95%; margin: 0 auto; }
        button { width: 100%; font-size: 18px; }
        input { width: 100%; font-size: 16px; }
    }

    body.mobile { font-size: 16px; }
    body.mobile button { width: 100%; font-size: 18px; }
    body.mobile input { width: 100%; font-size: 16px; }
    </style>

    <h1>전체 우산 대여 페이지</h1>
    <p style="color:red;">{{ message }}</p>
    <form method="POST" id="umbrellaForm">
        <input type="text" name="student_id" id="student_id" placeholder="학번 입력" value="{{ student_id }}">
        <small>정확한 학번을 입력해주세요 (10자리 숫자)</small>
        <br><br>
        {% for u in umbrellas %}
            <div style="margin-bottom:10px;">
                <strong>{{ u.id }}번 우산:</strong>
                {% if u.status == 'available' %}
                    🟢 사용 가능
                    <button type="submit" name="rent_id" value="{{ u.id }}" class="rentBtn">대여하기</button>
                {% else %}
                    🔴 대여 중
                    {% if u.student_id == student_id %}
                        <button type="submit" name="return_id" value="{{ u.id }}" class="returnBtn">반납하기</button>
                    {% endif %}
                {% endif %}
            </div>
        {% endfor %}
    </form>

    <!-- 학번 유효성 체크 및 버튼 활성화 -->
    <script>
    const studentInput = document.getElementById("student_id");
    const rentBtns = document.querySelectorAll(".rentBtn");
    const returnBtns = document.querySelectorAll(".returnBtn");

    function validateStudentID(sid){
        return /^\\d{4}304\\d{3}$/.test(sid);
    }

    function updateButtons(){
        const sid = studentInput.value;
        const valid = validateStudentID(sid);
        rentBtns.forEach(b => b.disabled = !valid);
        returnBtns.forEach(b => b.disabled = !valid);
    }

    studentInput.addEventListener("input", updateButtons);
    window.addEventListener("load", updateButtons);
    </script>
    """

    return render_template_string(html_all, umbrellas=umbrellas, student_id=student_id, message=message)

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
        if valid_student_id(student_id):
            cur.execute("SELECT status, student_id FROM umbrellas WHERE id=?", (num,))
            u = cur.fetchone()
            if u["status"] == "available":
                cur.execute("UPDATE umbrellas SET status='rented', student_id=? WHERE id=?", (student_id, num))
                conn.commit()
                message = f"{num}번 우산 대여 완료"
            elif u["student_id"] == student_id:
                cur.execute("UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?", (num,))
                conn.commit()
                message = f"{num}번 우산 반납 완료"
            else:
                message = "이 우산을 빌린 학번만 반납 가능합니다."
        else:
            message = "정확한 학번을 입력해주세요."

    cur.execute("SELECT * FROM umbrellas WHERE id=?", (num,))
    u = cur.fetchone()

    html_single = """
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <!-- 모바일 즉시 대응 JS -->
    <script>
    (function(){
        if (/Mobi|Android/i.test(navigator.userAgent)) {
            document.body.classList.add('mobile');
            document.body.style.display='none';
            document.body.offsetHeight;
            document.body.style.display='';
        }
    })();
    </script>

    <!-- 모바일 대응 CSS -->
    <style>
    body { font-family: Arial, sans-serif; }

    @media (max-width: 768px) {
        body { font-size: 16px; }
        button { width: 100%; font-size: 18px; }
        input { width: 100%; font-size: 16px; }
    }

    body.mobile { font-size: 16px; }
    body.mobile button { width: 100%; font-size: 18px; }
    body.mobile input { width: 100%; font-size: 16px; }
    </style>

    <h2>{{ u.id }}번 우산 상태: {{ u.status }}{% if u.status=='rented' %} (학번: {{ u.student_id }}){% endif %}</h2>
    <p style="color:red;">{{ message }}</p>
    <form method="POST" id="umbrellaForm">
        <input type="text" name="student_id" id="student_id" placeholder="학번 입력" value="">
        <small>정확한 학번을 입력해주세요 (10자리 숫자)</small>
        <br><br>
        {% if u.status=='available' or u.student_id==request.form.get('student_id') %}
            <button type="submit" id="actionBtn">{% if u.status=='available' %}대여하기{% else %}반납하기{% endif %}</button>
        {% endif %}
    </form>

    <!-- 학번 유효성 체크 및 버튼 활성화 -->
    <script>
    const studentInput = document.getElementById("student_id");
    const actionBtn = document.getElementById("actionBtn");

    function validateStudentID(sid){
        return /^\\d{4}304\\d{3}$/.test(sid);
    }

    function updateButton(){
        const sid = studentInput.value;
        if(actionBtn) actionBtn.disabled = !validateStudentID(sid);
    }

    studentInput.addEventListener("input", updateButton);
    window.addEventListener("load", updateButton);
    </script>
    """

    return render_template_string(html_single, u=u, message=message)

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
        cur.execute("UPDATE umbrellas SET status='available', student_id=NULL WHERE id=?", (force_return_id,))
        conn.commit()

    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    html_admin = """
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
    return render_template_string(html_admin, umbrellas=umbrellas)

# ------------------
if __name__ == "__main__":
    app.run(debug=True)