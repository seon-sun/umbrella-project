from flask import Flask, request, render_template_string, redirect
import psycopg2
import psycopg2.extras
import os
import re
import requests
from datetime import datetime, timezone, timedelta

app = Flask(__name__)

# ------------------
# 메모리 캐시
# ------------------
_umbrella_cache = None

def get_cache():
    global _umbrella_cache
    if _umbrella_cache is None:
        refresh_cache()
    return _umbrella_cache

def refresh_cache():
    global _umbrella_cache
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, status, student_id, student_name FROM umbrellas ORDER BY id")
        _umbrella_cache = [dict(u) for u in cur.fetchall()]
    finally:
        conn.close()

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
            student_name TEXT,
            rented_at TIMESTAMP
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
# ✅ 디스코드 알림
# ------------------
def send_discord(msg):
    token = os.environ.get("DISCORD_BOT_TOKEN")
    channel_id = os.environ.get("DISCORD_CHANNEL_ID")
    if not token or not channel_id:
        print("[Discord] 환경변수 없음")
        return
    try:
        res = requests.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
            json={"content": msg},
            timeout=3
        )
        print(f"[Discord] {res.status_code} / {res.text}")
    except Exception as e:
        print(f"[Discord] 실패: {e}")

# ------------------
# ✅ 연체 알림 스케줄러 (매일 KST 09:30 = UTC 00:30)
# ------------------
def check_overdue():
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, student_name, student_id, rented_at
            FROM umbrellas
            WHERE status='rented' AND rented_at IS NOT NULL
        """)
        rows = cur.fetchall()
        for row in rows:
            rented_at = row["rented_at"]
            if rented_at.tzinfo is None:
                rented_at = rented_at.replace(tzinfo=timezone.utc)
            rented_at_kst = rented_at.astimezone(kst)
            days = (now.date() - rented_at_kst.date()).days
            if days >= 6:  # 6일째 = 1일 연체
                overdue_days = days - 5
                send_discord(
                    f"⚠️ [연체 {overdue_days}일차] {row['student_name']} / {row['student_id']} → {row['id']}번 우산 "
                    f"(대여일: {rented_at_kst.strftime('%Y-%m-%d')})"
                )
    finally:
        conn.close()

# ------------------
# ✅ UptimeRobot 헬스체크 엔드포인트 (연체 알림 트리거)
# ------------------
_last_overdue_check = None

@app.route("/health")
def health():
    global _last_overdue_check
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    # 매일 09:30 KST에 한 번만 실행
    today_check_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if now >= today_check_time:
        check_key = now.strftime("%Y-%m-%d")
        if _last_overdue_check != check_key:
            _last_overdue_check = check_key
            check_overdue()
    return "OK", 200

# ------------------
# ✅ 폴링 엔드포인트 (실시간 동기화)
# ------------------
@app.route("/u/status", methods=["GET"])
def umbrella_status():
    return {"umbrellas": get_cache()}

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

            now_kst = datetime.now(timezone(timedelta(hours=9)))
            cur.execute(
                "UPDATE umbrellas SET status='rented', student_id=%s, student_name=%s, rented_at=%s WHERE id=%s",
                (student_id, student_name, now_kst, uid)
            )
            conn.commit()
            refresh_cache()
            send_discord(f"🟢 [대여] {student_name} / {student_id} → {uid}번 우산")
            return {"ok": True, "msg": f"{uid}번 우산 대여 완료", "new_status": "rented",
                    "student_id": student_id, "student_name": student_name}

        elif action == "return":
            cur.execute("SELECT student_id, student_name FROM umbrellas WHERE id=%s", (uid,))
            umbrella = cur.fetchone()
            if not umbrella or umbrella["student_id"] != student_id or umbrella["student_name"] != student_name:
                return {"ok": False, "msg": "본인이 대여한 우산만 반납 가능합니다."}

            cur.execute(
                "UPDATE umbrellas SET status='available', student_id=NULL, student_name=NULL, rented_at=NULL WHERE id=%s",
                (uid,)
            )
            conn.commit()
            refresh_cache()
            send_discord(f"🔴 [반납] {student_name} / {student_id} → {uid}번 우산")
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
            "UPDATE umbrellas SET status=%s, student_id=NULL, student_name=NULL, rented_at=NULL WHERE id=%s",
            (status, uid)
        )
        conn.commit()
        refresh_cache()
        if action == "broken":
            send_discord(f"🟡 [분실/고장] {uid}번 우산")
        elif action == "recover":
            send_discord(f"✅ [복구] {uid}번 우산")
    finally:
        conn.close()

    return {"ok": True}

# ------------------
# 전체 우산 페이지
# ------------------
@app.route("/u/all", methods=["GET"])
def all_umbrellas():
    message = ""
    student_id = ""
    student_name = ""
    umbrellas = get_cache()

    html_all = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>동백 우산 대여</title>
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html { font-size: 18px; }
    html, body { width: 100%; overflow-x: hidden; }
    body { font-family: 'Noto Sans KR', sans-serif; background: #fff; color: #222; -webkit-text-size-adjust: none; text-size-adjust: none; }
    .wrap { width: 100%; background: #fff; min-height: 100vh; padding: 24px 16px 40px; }
    h1 { font-size: 1.5rem; font-weight: 700; margin-bottom: 6px; }
    .subtitle { font-size: 0.85rem; color: #888; margin-bottom: 20px; }
    .input-row { display: flex; flex-direction: column; gap: 10px; margin-bottom: 8px; }
    .input-row input { width: 100%; padding: 14px 16px; border: 1.5px solid #ddd; border-radius: 10px; font-size: 1rem; outline: none; transition: border 0.2s; font-family: 'Noto Sans KR', sans-serif; }
    .input-row input:focus { border-color: #4a90e2; }
    .hint { font-size: 0.78rem; color: #aaa; margin-bottom: 20px; }
    .msg { font-size: 0.85rem; color: #e74c3c; min-height: 20px; margin-bottom: 16px; font-weight: 500; }
    .umbrella-list { display: flex; flex-direction: column; gap: 10px; }
    .umbrella-item { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; border-radius: 12px; background: #f8f9fb; border: 1.5px solid #eee; }
    .umbrella-item .label { font-size: 1rem; font-weight: 600; }
    .umbrella-item .status { font-size: 0.85rem; color: #888; margin-left: 8px; }
    .btn-rent { padding: 12px 18px; background: #4a90e2; color: #fff; border: none; border-radius: 8px; font-size: 0.9rem; font-weight: 600; cursor: pointer; min-width: 72px; font-family: 'Noto Sans KR', sans-serif; }
    .btn-rent:disabled { background: #c8d6e5; cursor: not-allowed; }
    .btn-return { padding: 12px 18px; background: #fff; color: #e74c3c; border: 1.5px solid #e74c3c; border-radius: 8px; font-size: 0.9rem; font-weight: 600; cursor: pointer; min-width: 72px; font-family: 'Noto Sans KR', sans-serif; }
    .btn-return:disabled { color: #ccc; border-color: #ddd; cursor: not-allowed; }
    </style>
</head>
<body>
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
                    <span class="status" id="status-{{ u.id }}" data-status="available">🟢 사용 가능</span>
                {% elif u.status == 'broken' %}
                    <span class="status" id="status-{{ u.id }}" data-status="broken">🟡 분실/고장</span>
                {% else %}
                    <span class="status" id="status-{{ u.id }}" data-status="rented">🔴 대여 중</span>
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

    // ✅ 2초 폴링 - 다른 기기에서 변경된 상태 실시간 반영
    setInterval(async () => {
        try {
            const res = await fetch('/u/status');
            const data = await res.json();
            const { sid, name } = getInputs();

            data.umbrellas.forEach(u => {
                const statusEl = document.getElementById('status-' + u.id);
                const btnsEl = document.getElementById('btns-' + u.id);
                if (!statusEl || !btnsEl) return;

                const currentStatus = statusEl.dataset.status;
                if (currentStatus === u.status) return; // 변경 없으면 스킵

                statusEl.dataset.status = u.status;

                if (u.status === 'available') {
                    statusEl.textContent = '🟢 사용 가능';
                    btnsEl.innerHTML = `<button class="btn-rent" onclick="doRent(${u.id})">대여</button>`;
                } else if (u.status === 'broken') {
                    statusEl.textContent = '🟡 분실/고장';
                    btnsEl.innerHTML = `<button class="btn-rent btn-broken-state" disabled>분실/고장</button>`;
                } else if (u.status === 'rented') {
                    statusEl.textContent = '🔴 대여 중';
                    const isOwner = u.student_id === sid && u.student_name === name;
                    btnsEl.innerHTML = `<button class="btn-return" data-owner-id="${u.student_id}" data-owner-name="${u.student_name}" onclick="doReturn(${u.id}, this)" ${isOwner ? '' : 'disabled'}>반납</button>`;
                }
                updateButtons();
            });
        } catch(e) {}
    }, 3000);

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
</body>
</html>
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

    umbrellas = get_cache()

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
            btnsEl.innerHTML = `<button class="btn-recover" onclick="doAction(${id}, 'recover')">복구</button>`;
        } else if (action === 'recover') {
            infoEl.textContent = '🟢 사용 가능';
            btnsEl.innerHTML = `<button class="btn-broken" onclick="doAction(${id}, 'broken')">분실/고장 처리</button>`;
        }
    }

    // ✅ 2초 폴링 - 관리자 페이지 실시간 동기화
    setInterval(async () => {
        try {
            const res = await fetch('/u/status');
            const data = await res.json();

            data.umbrellas.forEach(u => {
                const infoEl = document.getElementById('info-' + u.id);
                const btnsEl = document.getElementById('btns-' + u.id);
                const item = document.getElementById('item-' + u.id);
                if (!infoEl || !btnsEl || !item) return;

                const currentStatus = item.dataset.status;
                if (currentStatus === u.status) return;

                item.dataset.status = u.status;

                if (u.status === 'rented') {
                    infoEl.textContent = '🔴 ' + (u.student_name || '') + ' / ' + (u.student_id || '');
                    btnsEl.innerHTML = `<button class="btn-broken" onclick="doAction(${u.id}, 'broken')">분실/고장 처리</button>`;
                } else if (u.status === 'broken') {
                    infoEl.textContent = '🟡 분실/고장';
                    btnsEl.innerHTML = `<button class="btn-recover" onclick="doAction(${u.id}, 'recover')">복구</button>`;
                } else if (u.status === 'available') {
                    infoEl.textContent = '🟢 사용 가능';
                    btnsEl.innerHTML = `<button class="btn-broken" onclick="doAction(${u.id}, 'broken')">분실/고장 처리</button>`;
                }
            });
        } catch(e) {}
    }, 3000);
    </script>
    """
    return render_template_string(html_admin, umbrellas=umbrellas)

# ------------------
if __name__ == "__main__":
    app.run(debug=True)