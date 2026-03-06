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
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', Arial, sans-serif; background: #f5f6fa; color: #333; }
    .wrap { max-width: 700px; margin: 40px auto; background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); padding: 32px; }
    h1 { font-size: 22px; font-weight: 700; margin-bottom: 6px; }
    .subtitle { font-size: 13px; color: #888; margin-bottom: 24px; }
    .input-row { display: flex; gap: 10px; margin-bottom: 6px; }
    .input-row input { flex: 1; padding: 9px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; outline: none; transition: border 0.2s; }
    .input-row input:focus { border-color: #4a90e2; }
    .hint { font-size: 12px; color: #aaa; margin-bottom: 20px; }
    .msg { font-size: 13px; color: #e74c3c; min-height: 18px; margin-bottom: 16px; }
    .umbrella-list { display: flex; flex-direction: column; gap: 8px; }
    .umbrella-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-radius: 8px; background: #f9f9f9; border: 1px solid #eee; }
    .umbrella-item .label { font-size: 14px; font-weight: 500; }
    .umbrella-item .status { font-size: 13px; color: #888; margin-left: 8px; }
    .btn-rent { padding: 6px 16px; background: #4a90e2; color: #fff; border: none; border-radius: 6px; font-size: 13px; cursor: pointer; }
    .btn-rent:disabled { background: #ccc; cursor: not-allowed; }
    .btn-return { padding: 6px 16px; background: #fff; color: #e74c3c; border: 1px solid #e74c3c; border-radius: 6px; font-size: 13px; cursor: pointer; }
    .btn-return:disabled { color: #ccc; border-color: #ccc; cursor: not-allowed; }

    /* 모바일 */
    @media (max-width: 768px) {
        .wrap { margin: 0; border-radius: 0; box-shadow: none; padding: 20px; }
        .input-row { flex-direction: column; gap: 8px; }
        .input-row input { font-size: 16px; padding: 10px 12px; }
        .btn-rent, .btn-return { width: 80px; font-size: 14px; padding: 8px 0; }
    }
    </style>

    <div class="wrap">
    <h1>🌂 동백 우산 대여</h1>
    <div class="subtitle">이름과 학번을 입력 후 대여/반납해주세요</div>
    <p class="msg">{{ message }}</p>
    <form method="POST" id="umbrellaForm">
        <div class="input-row">
            <input type="text" name="student_name" id="student_name" placeholder="이름" value="{{ student_name }}">
            <input type="text" name="student_id" id="student_id" placeholder="학번 (10자리)" value="{{ student_id }}">
        </div>
        <div class="hint">학번 형식: 20XX304XXX</div>
        <div class="umbrella-list">
        {% for u in umbrellas %}
            <div class="umbrella-item">
                <div>
                    <span class="label">{{ u.id }}번 우산</span>
                    {% if u.status == 'available' %}
                        <span class="status">🟢 사용 가능</span>
                    {% else %}
                        <span class="status">🔴 대여 중</span>
                    {% endif %}
                </div>
                {% if u.status == 'available' %}
                    <button type="submit" name="rent_id" value="{{ u.id }}" class="btn-rent rentBtn">대여</button>
                {% else %}
                    <button type="submit" name="return_id" value="{{ u.id }}" class="btn-return returnBtn"
                            data-owner-id="{{ u.student_id }}"
                            data-owner-name="{{ u.student_name }}"
                            {% if u.student_id != student_id or u.student_name != student_name %}disabled{% endif %}>반납</button>
                {% endif %}
            </div>
        {% endfor %}
        </div>
    </form>
    </div>

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
# 관리자페이지
# ------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_page():
    admin_pass = "0927"
    input_pass = request.args.get("pass")
    if input_pass != admin_pass:
        return "관리자페이지인증. URL 뒤에 ?pass=비밀번호입력."

    force_return_id = request.form.get("force_return_id")
    if force_return_id:
        conn = get_db()
        try:
            conn.execute(
                "UPDATE umbrellas SET status='available', student_id=NULL, student_name=NULL WHERE id=?",
                (force_return_id,)
            )
            conn.commit()
        finally:
            conn.close()
        return redirect("/admin?pass=0927")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM umbrellas ORDER BY id")
    umbrellas = cur.fetchall()

    html_admin = """
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', Arial, sans-serif; background: #f5f6fa; color: #333; }
    .wrap { max-width: 700px; margin: 40px auto; background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); padding: 32px; }
    h1 { font-size: 22px; font-weight: 700; margin-bottom: 24px; }
    .umbrella-list { display: flex; flex-direction: column; gap: 8px; }
    .umbrella-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-radius: 8px; background: #f9f9f9; border: 1px solid #eee; }
    .umbrella-item .label { font-size: 14px; font-weight: 500; }
    .umbrella-item .info { font-size: 13px; color: #555; margin-left: 8px; }
    .btn-force { padding: 6px 14px; background: #fff; color: #e74c3c; border: 1px solid #e74c3c; border-radius: 6px; font-size: 13px; cursor: pointer; white-space: nowrap; }
    .btn-force:hover { background: #e74c3c; color: #fff; }
    @media (max-width: 768px) {
        .wrap { margin: 0; border-radius: 0; box-shadow: none; padding: 20px; }
        .umbrella-item { font-size: 13px; }
        .btn-force { font-size: 12px; padding: 5px 10px; }
    }
    </style>
    <div class="wrap">
    <h1>🔧 관리자 페이지</h1>
    <div class="umbrella-list">
        {% for u in umbrellas %}
            <div class="umbrella-item">
                <div>
                    <span class="label">{{ u.id }}번 우산</span>
                    {% if u.status == 'rented' %}
                        <span class="info">🔴 {{ u.student_name or '' }} / {{ u.student_id or '' }}</span>
                    {% else %}
                        <span class="info">🟢 사용 가능</span>
                    {% endif %}
                </div>
                {% if u.status == 'rented' %}
                    <form method="POST" action="/admin?pass=0927" style="margin:0;">
                        <button type="submit" name="force_return_id" value="{{ u.id }}" class="btn-force">강제 반납</button>
                    </form>
                {% endif %}
            </div>
        {% endfor %}
    </div>
    </div>
    """
    return render_template_string(html_admin, umbrellas=umbrellas)

# ------------------
if __name__ == "__main__":
    app.run(debug=True)