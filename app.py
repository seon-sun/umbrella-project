from flask import Flask, request, render_template_string, redirect
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
    return bool(re.fullmatch(r"\d{4}304\d{3}", sid))

# ------------------
# ✅ UptimeRobot 헬스체크 엔드포인트
# ------------------
@app.route("/health")
def health():
    return "OK", 200

# ------------------
# 전체 우산 페이지
# ------------------
@app.route("/u/all", methods=["GET", "POST"])
def all_umbrellas():
    conn = get_db()
    cur = conn.cursor()
    message = ""
    student_id = request.form.get("student_id") or ""
    student_name = request.form.get("student_name") or ""
    rent_id = request.form.get("rent_id")
    return_id = request.form.get("return_id")

    # 학번 + 이름 둘 다 유효한지 확인
    valid = valid_student_id(student_id) and len(student_name.strip()) > 0

    # ---------------- 대여 처리 ----------------
    if rent_id and valid:
        # ✅ 학번 + 이름 세트로 대여 수 카운트
        cur.execute(
            "SELECT COUNT(*) as cnt FROM umbrellas WHERE student_id=? AND student_name=?",
            (student_id, student_name.strip())
        )
        rented_count = cur.fetchone()["cnt"]

        cur.execute("SELECT status FROM umbrellas WHERE id=?", (rent_id,))
        umbrella = cur.fetchone()
        if umbrella["status"] == "available":
            if rented_count >= 2:
                message = "더 이상 대여 불가 (2개 제한)"
            else:
                with conn:
                    cur.execute(
                        "UPDATE umbrellas SET status='rented', student_id=?, student_name=? WHERE id=?",
                        (str(student_id), str(student_name.strip()), rent_id)
                    )
                message = f"{rent_id}번 우산 대여 완료"
        else:
            message = "이미 대여 중인 우산입니다."

    # ---------------- 반납 처리 ----------------
    elif return_id and valid:
        # ✅ 학번 + 이름 둘 다 일치해야 반납 가능
        cur.execute(
            "SELECT status, student_id, student_name FROM umbrellas WHERE id=?",
            (return_id,)
        )
        umbrella = cur.fetchone()
        if umbrella["student_id"] == student_id and umbrella["student_name"] == student_name.strip():
            with conn:
                cur.execute(
                    "UPDATE umbrellas SET status='available', student_id=NULL, student_name=NULL WHERE id=?",
                    (return_id,)
                )
            message = f"{return_id}번 우산 반납 완료"
        else:
            message = "본인이 대여한 우산만 반납 가능합니다."

    # 전체 우산 조회
    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    html_all = """
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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

    <h1>동백 우산 대여 페이지</h1>
    <p style="color:red;">{{ message }}</p>
    <form method="POST" id="umbrellaForm">
        <input type="text" name="student_id" id="student_id" placeholder="학번 입력 (10자리)" value="{{ student_id }}">
        <br><br>
        <input type="text" name="student_name" id="student_name" placeholder="이름 입력" value="{{ student_name }}">
        <br>
        <small>학번(10자리)과 이름을 모두 입력해주세요</small>
        <br><br>
        {% for u in umbrellas %}
            <div style="margin-bottom:10px;">
                <strong>{{ u.id }}번 우산:</strong>
                {% if u.status == 'available' %}
                    🟢 사용 가능
                    <button type="submit" name="rent_id" value="{{ u.id }}" class="rentBtn">대여하기</button>
                {% else %}
                    🔴 대여 중
                    <button type="submit" name="return_id" value="{{ u.id }}" class="returnBtn"
                            data-owner-id="{{ u.student_id }}"
                            data-owner-name="{{ u.student_name }}"
                            {% if u.student_id != student_id or u.student_name != student_name %}disabled{% endif %}>반납하기</button>
                {% endif %}
            </div>
        {% endfor %}
    </form>

    <script>
    document.addEventListener("DOMContentLoaded", function(){
        // 1️⃣ 모바일 UI 즉시 적용
        const ua = navigator.userAgent || '';
        const isMobileUA = /Mobi|Android|iPhone|iPad|iPod/i.test(ua);
        const isNarrow = window.matchMedia("(max-width:768px)").matches;
        if(isMobileUA || isNarrow) document.body.classList.add('mobile');

        // 2️⃣ 버튼 활성화 (학번 + 이름 세트로 확인)
        const studentInput = document.getElementById("student_id");
        const nameInput = document.getElementById("student_name");
        const rentBtns = document.querySelectorAll(".rentBtn");
        const returnBtns = document.querySelectorAll(".returnBtn");

        function validateStudentID(sid){ return /^\d{4}304\d{3}$/.test(sid); }

        function updateButtons(){
            const sid = studentInput.value;
            const name = nameInput.value.trim();
            const valid = validateStudentID(sid) && name.length > 0;
            rentBtns.forEach(b => b.disabled = !valid);
            returnBtns.forEach(b => {
                const ownerId = b.dataset.ownerId || '';
                const ownerName = b.dataset.ownerName || '';
                // ✅ 학번 + 이름 둘 다 일치해야 반납 버튼 활성화
                b.disabled = (ownerId !== sid || ownerName !== name) || !valid;
            });
        }

        studentInput.addEventListener("input", updateButtons);
        nameInput.addEventListener("input", updateButtons);
        updateButtons();

        // 3️⃣ 엔터키 submit 방지
        document.getElementById('umbrellaForm').addEventListener('keypress', e => {
            if(e.key === 'Enter') e.preventDefault();
        });
    });
    </script>
    """

    return render_template_string(html_all, umbrellas=umbrellas, student_id=student_id, student_name=student_name, message=message)

# ------------------
# 관리자 페이지
# ------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_page():
    admin_pass = "0927"
    input_pass = request.args.get("pass")
    if input_pass != admin_pass:
        return "관리자 인증 필요. URL 뒤에 ?pass=비밀번호를 붙여주세요."

    conn = get_db()
    cur = conn.cursor()
    force_return_id = request.form.get("force_return_id")
    if force_return_id:
        with conn:
            cur.execute(
                "UPDATE umbrellas SET status='available', student_id=NULL, student_name=NULL WHERE id=?",
                (force_return_id,)
            )
        return redirect("/admin?pass=0927")

    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    html_admin = """
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    body { font-family: Arial, sans-serif; padding: 10px; }
    h1 { font-size: 20px; }
    .umbrella-row {
        display: flex;
        align-items: center;
        flex-wrap: nowrap;
        gap: 6px;
        margin-bottom: 10px;
        font-size: 14px;
    }
    .umbrella-row .info {
        flex: 1;
        min-width: 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .umbrella-row button {
        flex-shrink: 0;
        font-size: 13px;
        padding: 4px 8px;
        white-space: nowrap;
    }
    @media (max-width: 768px) {
        body { font-size: 14px; }
        .umbrella-row { font-size: 13px; }
        .umbrella-row button { font-size: 12px; padding: 4px 6px; }
    }
    </style>
    <h1>관리자 페이지</h1>
    <form method="POST" action="/admin?pass=0927">
        {% for u in umbrellas %}
            <div class="umbrella-row">
                <div class="info">
                    <strong>{{ u.id }}번</strong>
                    {% if u.status == 'rented' %}
                        🔴 {{ u.student_id or '' }} / {{ u.student_name or '' }}
                    {% else %}
                        🟢 사용 가능
                    {% endif %}
                </div>
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