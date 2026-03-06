from flask import Flask, request, render_template_string, redirect
import psycopg2
import psycopg2.extras
import os
import re

app = Flask(__name__)

# ------------------
# DB 연결
# ------------------
def get_db():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    return conn

# ------------------
# DB 초기화 (테이블 + 우산 30개)
# ------------------
def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS umbrellas (
            id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'available',
            student_id TEXT,
            student_name TEXT
        )
    """)
    cur.execute("SELECT COUNT(*) as cnt FROM umbrellas")
    if cur.fetchone()[0] == 0:
        for i in range(1, 31):
            cur.execute("INSERT INTO umbrellas (id) VALUES (%s)", (i,))
    conn.commit()
    conn.close()

init_db()

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
# ✅ AJAX 대여/반납 엔드포인트
# ------------------
@app.route("/u/action", methods=["POST"])
def umbrella_action():
    data = request.get_json()
    action = data.get("action")
    uid = str(data.get("id"))
    student_id = data.get("student_id", "").strip()
    student_name = data.get("student_name", "").strip()

    if not valid_student_id(student_id) or not student_name:
        return {"ok": False, "msg": "학번 또는 이름이 올바르지 않습니다."}, 400

    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if action == "rent":
            cur.execute("SELECT COUNT(*) as cnt FROM umbrellas WHERE student_id=%s", (student_id,))
            rented_count = cur.fetchone()["cnt"]
            if rented_count >= 2:
                return {"ok": False, "msg": "더 이상 대여 불가 (2개 제한)"}

            cur.execute("SELECT status FROM umbrellas WHERE id=%s", (uid,))
            umbrella = cur.fetchone()
            if not umbrella or umbrella["status"] != "available":
                return {"ok": False, "msg": "이미 대여 중인 우산입니다."}

            cur.execute(
                "UPDATE umbrellas SET status='rented', student_id=%s, student_name=%s WHERE id=%s",
                (student_id, student_name, uid)
            )
            conn.commit()
            return {"ok": True, "msg": f"{uid}번 우산 대여 완료", "new_status": "rented",
                    "student_id": student_id, "student_name": student_name}

        elif action == "return":
            cur.execute("SELECT student_id, student_name FROM umbrellas WHERE id=%s", (uid,))
            umbrella = cur.fetchone()
            if not umbrella or umbrella["student_id"] != student_id or umbrella["student_name"] != student_name:
                return {"ok": False, "msg": "본인이 대여한 우산만 반납 가능합니다."}

            cur.execute(
                "UPDATE umbrellas SET status='available', student_id=NULL, student_name=NULL WHERE id=%s",
                (uid,)
            )
            conn.commit()
            return {"ok": True, "msg": f"{uid}번 우산 반납 완료", "new_status": "available"}

        return {"ok": False, "msg": "알 수 없는 action"}, 400
    finally:
        conn.close()

# ------------------
# ✅ AJAX 관리자 처리 엔드포인트
# ------------------
@app.route("/admin/action", methods=["POST"])
def admin_action():
    admin_pass = request.args.get("pass")
    if admin_pass != "0927":
        return {"ok": False, "msg": "인증 실패"}, 403

    data = request.get_json()
    action = data.get("action")
    uid = data.get("id")

    if action == "broken":
        status = "broken"
    elif action == "recover":
        status = "available"
    else:
        return {"ok": False, "msg": "알 수 없는 action"}, 400

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE umbrellas SET status=%s, student_id=NULL, student_name=NULL WHERE id=%s",
            (status, uid)
        )
        conn.commit()
    finally:
        conn.close()

    return {"ok": True}

# ------------------
# 전체 우산 페이지
# ------------------
@app.route("/u/all", methods=["GET"])
def all_umbrellas():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    message = ""
    student_id = ""
    student_name = ""

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
    <p class="msg" id="msgBox">{{ message }}</p>
    <div class="input-row">
        <input type="text" id="student_name" placeholder="이름" value="{{ student_name }}">
        <input type="text" id="student_id" placeholder="학번 (10자리)" value="{{ student_id }}">
    </div>
    <div class="hint">학번 형식: 10자리 숫자</div>
    <div class="umbrella-list" style="margin-top:16px;">
    {% for u in umbrellas %}
        <div class="umbrella-item" id="item-{{ u.id }}">
            <div>
                <span class="label">{{ u.id }}번 우산</span>
                {% if u.status == 'available' %}
                    <span class="status" id="status-{{ u.id }}">🟢 사용 가능</span>
                {% elif u.status == 'broken' %}
                    <span class="status" id="status-{{ u.id }}">🟡 분실/고장</span>
                {% else %}
                    <span class="status" id="status-{{ u.id }}">🔴 대여 중</span>
                {% endif %}
            </div>
            <div id="btns-{{ u.id }}">
            {% if u.status == 'available' %}
                <button class="btn-rent" onclick="doRent({{ u.id }})">대여</button>
            {% elif u.status == 'broken' %}
                <button class="btn-rent btn-broken-state" disabled>분실/고장</button>
            {% else %}
                <button class="btn-return"
                    data-owner-id="{{ u.student_id }}"
                    data-owner-name="{{ u.student_name }}"
                    onclick="doReturn({{ u.id }}, this)">반납</button>
            {% endif %}
            </div>
        </div>
    {% endfor %}
    </div>
    </div>

    <script>
    const studentInput = document.getElementById("student_id");
    const nameInput = document.getElementById("student_name");
    const msgBox = document.getElementById("msgBox");

    function validateStudentID(sid){ return /^\d{4}304\d{3}$/.test(sid); }

    function getInputs() {
        return {
            sid: studentInput.value.trim(),
            name: nameInput.value.trim()
        };
    }

    function isValid() {
        const { sid, name } = getInputs();
        return validateStudentID(sid) && name.length > 0;
    }

    function updateButtons() {
        const { sid, name } = getInputs();
        const valid = validateStudentID(sid) && name.length > 0;
        // ✅ broken 상태 버튼 제외하고 모든 대여 버튼 활성화/비활성화
        document.querySelectorAll(".btn-rent").forEach(b => {
            if (!b.classList.contains("btn-broken-state")) {
                b.disabled = !valid;
            }
        });
        document.querySelectorAll(".btn-return").forEach(b => {
            const ownerId = b.dataset.ownerId || '';
            const ownerName = b.dataset.ownerName || '';
            b.disabled = (ownerId !== sid || ownerName !== name) || !valid;
        });
    }

    studentInput.addEventListener("input", updateButtons);
    nameInput.addEventListener("input", updateButtons);
    updateButtons();

    async function doRent(id) {
        if (!isValid()) return;
        const { sid, name } = getInputs();
        const btn = document.querySelector('#btns-' + id + ' button');
        btn.disabled = true;

        const res = await fetch('/u/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'rent', id: id, student_id: sid, student_name: name })
        });
        const data = await res.json();
        msgBox.textContent = data.msg;

        if (data.ok) {
            document.getElementById('status-' + id).textContent = '🔴 대여 중';
            document.getElementById('btns-' + id).innerHTML =
                '<button class="btn-return" data-owner-id="' + sid + '" data-owner-name="' + name + '" onclick="doReturn(' + id + ', this)">반납</button>';
            updateButtons();
        } else {
            btn.disabled = false;
        }
    }

    async function doReturn(id, btn) {
        if (!isValid()) return;
        const { sid, name } = getInputs();
        btn.disabled = true;

        const res = await fetch('/u/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'return', id: id, student_id: sid, student_name: name })
        });
        const data = await res.json();
        msgBox.textContent = data.msg;

        if (data.ok) {
            document.getElementById('status-' + id).textContent = '🟢 사용 가능';
            document.getElementById('btns-' + id).innerHTML =
                '<button class="btn-rent" onclick="doRent(' + id + ')">대여</button>';
            updateButtons();
        } else {
            btn.disabled = false;
        }
    }
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
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
    .umbrella-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-radius: 8px; background: #f9f9f9; border: 1px solid #eee; transition: background 0.2s; }
    .umbrella-item .label { font-size: 14px; font-weight: 500; }
    .umbrella-item .info { font-size: 13px; color: #555; margin-left: 8px; }
    .btn-broken { padding: 6px 14px; background: #fff; color: #e74c3c; border: 1px solid #e74c3c; border-radius: 6px; font-size: 13px; cursor: pointer; white-space: nowrap; }
    .btn-broken:hover { background: #e74c3c; color: #fff; }
    .btn-recover { padding: 6px 14px; background: #fff; color: #27ae60; border: 1px solid #27ae60; border-radius: 6px; font-size: 13px; cursor: pointer; white-space: nowrap; }
    .btn-recover:hover { background: #27ae60; color: #fff; }
    .btn-broken:disabled, .btn-recover:disabled { opacity: 0.4; cursor: not-allowed; }
    @media (max-width: 768px) {
        .wrap { margin: 0; border-radius: 0; box-shadow: none; padding: 20px; }
        .umbrella-item { font-size: 13px; }
        .btn-broken, .btn-recover { font-size: 12px; padding: 5px 10px; }
    }
    </style>
    <div class="wrap">
    <h1>🔧 관리자 페이지</h1>
    <div class="umbrella-list" id="umbrellaList">
        {% for u in umbrellas %}
            <div class="umbrella-item" id="item-{{ u.id }}" data-status="{{ u.status }}">
                <div>
                    <span class="label">{{ u.id }}번 우산</span>
                    {% if u.status == 'rented' %}
                        <span class="info" id="info-{{ u.id }}">🔴 {{ u.student_name or '' }} / {{ u.student_id or '' }}</span>
                    {% elif u.status == 'broken' %}
                        <span class="info" id="info-{{ u.id }}">🟡 분실/고장</span>
                    {% else %}
                        <span class="info" id="info-{{ u.id }}">🟢 사용 가능</span>
                    {% endif %}
                </div>
                <div style="display:flex; gap:6px;" id="btns-{{ u.id }}">
                {% if u.status == 'rented' or u.status == 'available' %}
                    <button class="btn-broken" onclick="doAction({{ u.id }}, 'broken')">분실/고장 처리</button>
                {% endif %}
                {% if u.status == 'broken' %}
                    <button class="btn-recover" onclick="doAction({{ u.id }}, 'recover')">복구</button>
                {% endif %}
                </div>
            </div>
        {% endfor %}
    </div>
    </div>
    <script>
    async function doAction(id, action) {
        const btns = document.querySelectorAll('#btns-' + id + ' button');
        btns.forEach(b => b.disabled = true);

        const res = await fetch('/admin/action?pass=0927', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: id, action: action })
        });

        if (!res.ok) {
            btns.forEach(b => b.disabled = false);
            alert('처리 실패');
            return;
        }

        // UI 즉시 업데이트 (새로고침 없음)
        const infoEl = document.getElementById('info-' + id);
        const btnsEl = document.getElementById('btns-' + id);

        if (action === 'broken') {
            infoEl.textContent = '🟡 분실/고장';
            btnsEl.innerHTML = '<button class="btn-recover" onclick="doAction(' + id + ', \'recover\')">복구</button>';
        } else if (action === 'recover') {
            infoEl.textContent = '🟢 사용 가능';
            btnsEl.innerHTML = '<button class="btn-broken" onclick="doAction(' + id + ', \'broken\')">분실/고장 처리</button>';
        }
    }
    </script>
    """
    return render_template_string(html_admin, umbrellas=umbrellas)

# ------------------
if __name__ == "__main__":
    app.run(debug=True)