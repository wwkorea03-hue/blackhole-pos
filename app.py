import os
import pymysql
from flask import Flask, request, render_template_string, redirect, url_for

app = Flask(__name__)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1828")

DEFAULT_DEPOSIT_MESSAGE = """⬇️⬇️⬇️ 구매시 ⬇️⬇️⬇️

입금금액 : 80,000
배송비 : 무료
예금주 : 조영민
은행명 : 우리은행
계좌번호 : 1005-104-856764
입금 후 성함 연락처 주소 부탁드립니다^^

⬆️⬆️⬆️ 구매시 ⬆️⬆️⬆️"""


def db():
    return pymysql.connect(
        host=os.getenv("MYSQLHOST"),
        port=int(os.getenv("MYSQLPORT")),
        user=os.getenv("MYSQLUSER"),
        password=os.getenv("MYSQLPASSWORD"),
        database=os.getenv("MYSQLDATABASE"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )


def init_db():
    conn = db()
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            `key` VARCHAR(100) PRIMARY KEY,
            `value` MEDIUMTEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            brand_name VARCHAR(255),
            brand_code VARCHAR(20),
            serial VARCHAR(20),
            client VARCHAR(255),
            division VARCHAR(255),
            wholesale INT,
            rate_name VARCHAR(100),
            rate_value FLOAT,
            shipping_fee INT DEFAULT 4000,
            retail INT,
            post_result MEDIUMTEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cur.execute("INSERT IGNORE INTO settings(`key`, `value`) VALUES ('account_holder', '조영민')")
        cur.execute("INSERT IGNORE INTO settings(`key`, `value`) VALUES ('bank_name', '우리은행')")
        cur.execute("INSERT IGNORE INTO settings(`key`, `value`) VALUES ('account_number', '1005-104-856764')")
        cur.execute("INSERT IGNORE INTO settings(`key`, `value`) VALUES ('deposit_message', %s)", (DEFAULT_DEPOSIT_MESSAGE,))

    conn.commit()
    conn.close()


def get_setting(key, default=""):
    conn = db()
    with conn.cursor() as cur:
        cur.execute("SELECT `value` FROM settings WHERE `key`=%s", (key,))
        row = cur.fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = db()
    with conn.cursor() as cur:
        cur.execute("""
        INSERT INTO settings(`key`, `value`)
        VALUES(%s, %s)
        ON DUPLICATE KEY UPDATE `value`=%s
        """, (key, value, value))
    conn.commit()
    conn.close()


def make_deposit_message(item):
    template = get_setting("deposit_message", DEFAULT_DEPOSIT_MESSAGE)
    holder = get_setting("account_holder", "조영민")
    bank = get_setting("bank_name", "우리은행")
    account = get_setting("account_number", "1005-104-856764")
    amount = f"{int(item.get('retail') or 0):,}"

    text = template
    import re
    text = re.sub(r"입금금액\s*:\s*.*", f"입금금액 : {amount}", text)
    text = re.sub(r"예금주\s*:\s*.*", f"예금주 : {holder}", text)
    text = re.sub(r"은행명\s*:\s*.*", f"은행명 : {bank}", text)
    text = re.sub(r"계좌번호\s*:\s*.*", f"계좌번호 : {account}", text)
    return text


HTML = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BLACKHOLE POS</title>
<style>
body { font-family: Arial, sans-serif; background:#f4f4f4; padding:12px; }
h2 { margin-top:0; }
.search { display:flex; gap:6px; margin-bottom:12px; }
input, textarea { width:100%; box-sizing:border-box; padding:10px; font-size:16px; }
button, .btn { padding:10px; font-size:15px; border:0; border-radius:8px; background:#222; color:white; text-decoration:none; display:inline-block; }
.card { background:white; padding:14px; border-radius:12px; margin-bottom:10px; box-shadow:0 1px 4px #ccc; }
.code { font-size:21px; font-weight:bold; margin-bottom:5px; }
.row { margin:4px 0; }
.copybox { width:100%; height:145px; margin-top:8px; }
.admin-link { display:block; margin:10px 0; color:#333; }
</style>
<script>
function copyText(id) {
    const el = document.getElementById(id);
    el.select();
    el.setSelectionRange(0, 999999);
    navigator.clipboard.writeText(el.value);
    alert("복사되었습니다.");
}
</script>
</head>
<body>

<h2>상품 검색</h2>
<a class="admin-link" href="/admin">계좌/입금메시지 관리</a>

<form method="get" class="search">
    <input name="q" placeholder="브랜드 / 코드 / 거래처 검색" value="{{ q }}">
    <button>검색</button>
</form>

{% for r in rows %}
<div class="card">
    <div class="code">{{ r.brand_code }} {{ r.serial }}</div>
    <div class="row">브랜드: {{ r.brand_name }}</div>
    <div class="row">거래처: {{ r.client }}</div>
    <div class="row">구분: {{ r.division or "" }}</div>
    <div class="row">도매가: {{ "{:,}".format(r.wholesale or 0) }}원</div>
    <div class="row">소매가: {{ "{:,}".format(r.retail or 0) }}원</div>

    <div class="row">등록일: {{ r.created_at.strftime('%Y-%m-%d %H:%M') }}</div>

    <textarea id="deposit{{ r.id }}" style="display:none;">{{ r.deposit_message }}</textarea>

    <button onclick="copyText('deposit{{ r.id }}')">
    입금요청 복사
    </button>
</div>
{% endfor %}

</body>
</html>
"""


ADMIN_HTML = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>관리</title>
<style>
body { font-family: Arial, sans-serif; background:#f4f4f4; padding:12px; }
.box { background:white; padding:14px; border-radius:12px; margin-bottom:12px; box-shadow:0 1px 4px #ccc; }
input, textarea { width:100%; box-sizing:border-box; padding:10px; font-size:16px; margin:4px 0 10px; }
button { padding:10px; font-size:16px; border:0; border-radius:8px; background:#222; color:white; }
textarea { height:210px; }
</style>
</head>
<body>

<h2>계좌 / 입금요청 관리</h2>

{% if not ok %}
<form method="post">
    <div class="box">
        <input type="password" name="password" placeholder="관리 비밀번호">
        <button>확인</button>
    </div>
</form>
{% else %}
<form method="post">
    <input type="hidden" name="password" value="{{ password }}">

    <div class="box">
        <h3>계좌정보</h3>
        예금주
        <input name="account_holder" value="{{ account_holder }}">
        은행명
        <input name="bank_name" value="{{ bank_name }}">
        계좌번호
        <input name="account_number" value="{{ account_number }}">
    </div>

    <div class="box">
        <h3>입금요청 메시지</h3>
        <textarea name="deposit_message">{{ deposit_message }}</textarea>
    </div>

    <button name="save" value="1">저장/수정</button>
    <button name="delete" value="1" style="background:#a00;">삭제</button>
</form>
{% endif %}

<p><a href="/">검색화면으로</a></p>

</body>
</html>
"""


@app.route("/")
def home():
    q = request.args.get("q", "").strip()

    conn = db()
    with conn.cursor() as cur:
        if q:
            cur.execute("""
            SELECT *
            FROM items
            WHERE brand_name LIKE %s
               OR brand_code LIKE %s
               OR serial LIKE %s
               OR client LIKE %s
               OR division LIKE %s
            ORDER BY id DESC
            LIMIT 100
            """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"))
        else:
            cur.execute("SELECT * FROM items ORDER BY id DESC LIMIT 100")

        rows = cur.fetchall()

    conn.close()

    for r in rows:
        r["deposit_message"] = make_deposit_message(r)

    return render_template_string(HTML, rows=rows, q=q)


@app.route("/admin", methods=["GET", "POST"])
def admin():
    ok = False
    password = ""

    if request.method == "POST":
        password = request.form.get("password", "")
        ok = password == ADMIN_PASSWORD

        if ok and request.form.get("save"):
            set_setting("account_holder", request.form.get("account_holder", ""))
            set_setting("bank_name", request.form.get("bank_name", ""))
            set_setting("account_number", request.form.get("account_number", ""))
            set_setting("deposit_message", request.form.get("deposit_message", ""))
            return redirect("/admin")

        if ok and request.form.get("delete"):
            set_setting("account_holder", "")
            set_setting("bank_name", "")
            set_setting("account_number", "")
            set_setting("deposit_message", "")
            return redirect("/admin")

    return render_template_string(
        ADMIN_HTML,
        ok=ok,
        password=password,
        account_holder=get_setting("account_holder", "조영민"),
        bank_name=get_setting("bank_name", "우리은행"),
        account_number=get_setting("account_number", "1005-104-856764"),
        deposit_message=get_setting("deposit_message", DEFAULT_DEPOSIT_MESSAGE)
    )


@app.route("/health")
def health():
    return "OK"


try:
    init_db()
except Exception as e:
    print("DB INIT ERROR:", e)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)