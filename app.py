import os
import re
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
        CREATE TABLE IF NOT EXISTS brands (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE,
            code VARCHAR(20) UNIQUE
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS divisions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS rates (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) UNIQUE,
            value FLOAT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            brand_name VARCHAR(255),
            brand_code VARCHAR(50),
            serial VARCHAR(50),
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

        cur.execute("""
        CREATE TABLE IF NOT EXISTS pos_search_cache (
            item_id INT PRIMARY KEY,
            code_text VARCHAR(120),
            brand_name VARCHAR(255),
            brand_code VARCHAR(50),
            serial VARCHAR(50),
            client VARCHAR(255),
            division VARCHAR(255),
            wholesale INT,
            retail INT,
            created_at DATETIME,
            search_text TEXT
        )
        """)

        for sql in [
            "ALTER TABLE items MODIFY brand_code VARCHAR(50)",
            "ALTER TABLE items MODIFY serial VARCHAR(50)",
            "ALTER TABLE items MODIFY brand_name VARCHAR(255)",
            "ALTER TABLE settings MODIFY `value` MEDIUMTEXT",
        ]:
            try:
                cur.execute(sql)
            except Exception:
                pass

        cur.execute("INSERT IGNORE INTO settings(`key`, `value`) VALUES ('account_holder', '조영민')")
        cur.execute("INSERT IGNORE INTO settings(`key`, `value`) VALUES ('bank_name', '우리은행')")
        cur.execute("INSERT IGNORE INTO settings(`key`, `value`) VALUES ('account_number', '1005-104-856764')")
        cur.execute("INSERT IGNORE INTO settings(`key`, `value`) VALUES ('deposit_message', %s)", (DEFAULT_DEPOSIT_MESSAGE,))
        cur.execute("INSERT IGNORE INTO rates(name, value) VALUES ('1.5배', 1.5)")

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


def normalize_search(value):
    text = str(value or "").lower()
    for x in [" ", "-", "_", "/", "."]:
        text = text.replace(x, "")
    return text


def make_deposit_message_from_amount(amount, selected_lines=None):
    template = get_setting("deposit_message", DEFAULT_DEPOSIT_MESSAGE)
    holder = get_setting("account_holder", "조영민")
    bank = get_setting("bank_name", "우리은행")
    account = get_setting("account_number", "1005-104-856764")

    text = template
    text = re.sub(r"입금금액\s*:\s*.*", f"입금금액 : {int(amount):,}", text)
    text = re.sub(r"예금주\s*:\s*.*", f"예금주 : {holder}", text)
    text = re.sub(r"은행명\s*:\s*.*", f"은행명 : {bank}", text)
    text = re.sub(r"계좌번호\s*:\s*.*", f"계좌번호 : {account}", text)

    if selected_lines:
        text = "\n".join(selected_lines) + "\n\n" + text

    return text


def make_deposit_message(item):
    return make_deposit_message_from_amount(item.get("retail") or 0)


def get_cache_count():
    try:
        conn = db()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM pos_search_cache")
            row = cur.fetchone()
        conn.close()
        return int(row["cnt"] or 0)
    except Exception:
        return 0


def rebuild_search_cache():
    conn = db()
    inserted = 0

    with conn.cursor() as cur:
        cur.execute("DELETE FROM pos_search_cache")
        cur.execute("""
        SELECT
            id,
            brand_name,
            brand_code,
            serial,
            client,
            division,
            wholesale,
            retail,
            created_at
        FROM items
        ORDER BY id
        """)
        rows = cur.fetchall()

        values = []
        for r in rows:
            code_text = f'{r.get("brand_code") or ""} {r.get("serial") or ""}'.strip()
            search_parts = [
                r.get("brand_name") or "",
                r.get("brand_code") or "",
                r.get("serial") or "",
                code_text,
                r.get("client") or "",
                r.get("division") or "",
            ]
            search_text = " ".join(search_parts)
            compact_text = normalize_search(search_text)
            full_search_text = f"{search_text} {compact_text}"

            values.append((
                r["id"],
                code_text,
                r.get("brand_name"),
                r.get("brand_code"),
                r.get("serial"),
                r.get("client"),
                r.get("division"),
                r.get("wholesale"),
                r.get("retail"),
                r.get("created_at"),
                full_search_text,
            ))

        if values:
            cur.executemany("""
            INSERT INTO pos_search_cache
            (
                item_id,
                code_text,
                brand_name,
                brand_code,
                serial,
                client,
                division,
                wholesale,
                retail,
                created_at,
                search_text
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, values)
            inserted = len(values)

        for sql in [
            "CREATE INDEX idx_cache_code_text ON pos_search_cache(code_text)",
            "CREATE INDEX idx_cache_brand_code ON pos_search_cache(brand_code)",
            "CREATE INDEX idx_cache_serial ON pos_search_cache(serial)",
            "CREATE INDEX idx_cache_client ON pos_search_cache(client)",
            "CREATE INDEX idx_cache_created_at ON pos_search_cache(created_at)",
        ]:
            try:
                cur.execute(sql)
            except Exception:
                pass

    conn.commit()
    conn.close()
    return inserted


def admin_ok():
    return request.values.get("password", "") == ADMIN_PASSWORD


BASE_STYLE = """
<style>
body { font-family: Arial, sans-serif; background:#f4f4f4; padding:12px; }
h2 { margin-top:0; }
a { color:#222; }
.search { display:flex; gap:6px; margin-bottom:12px; }
input, textarea, select { width:100%; box-sizing:border-box; padding:10px; font-size:16px; margin:4px 0 10px; }
button, .btn { padding:10px; font-size:15px; border:0; border-radius:8px; background:#222; color:white; text-decoration:none; display:inline-block; margin:2px 0; }
.btn-gray { background:#777; }
.btn-red { background:#a00; }
.card, .box { background:white; padding:14px; border-radius:12px; margin-bottom:10px; box-shadow:0 1px 4px #ccc; }
.code { font-size:21px; font-weight:bold; margin-bottom:5px; }
.row { margin:4px 0; }
.admin-link { display:block; margin:10px 0; color:#333; }
.check-area { position:absolute; right:12px; top:12px; font-size:14px; }
.selected-box { background:#fff; border-radius:12px; padding:12px; margin:10px 0; box-shadow:0 1px 4px #ccc; }
.selected-row { display:flex; justify-content:space-between; border-bottom:1px solid #eee; padding:5px 0; font-size:14px; }
.small { color:#666; font-size:13px; }
.notice { font-size:13px; color:#777; margin:6px 0 10px; }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.nav a { margin:2px; }
</style>
"""


HTML = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BLACKHOLE POS</title>
""" + BASE_STYLE + """
<script>
function money(n) {
    return Number(n || 0).toLocaleString();
}
function getSelected() {
    try { return JSON.parse(localStorage.getItem("selectedItems") || "[]"); }
    catch(e) { return []; }
}
function setSelected(items) {
    localStorage.setItem("selectedItems", JSON.stringify(items));
}
function renderSelected() {
    const box = document.getElementById("selectedList");
    const wrap = document.getElementById("selectedWrap");
    const items = getSelected();

    if (!items.length) {
        wrap.style.display = "none";
        box.innerHTML = "";
        return;
    }

    wrap.style.display = "block";
    let html = "";
    let total = 0;

    items.forEach((it, idx) => {
        total += Number(it.retail || 0);
        html += `
            <div class="selected-row">
                <span>${it.code} ${money(it.retail)}</span>
                <button type="button" onclick="removeSelected(${idx})" style="padding:4px 7px;font-size:12px;background:#a00;">삭제</button>
            </div>
        `;
    });

    html += `<div class="selected-row"><b>합계</b><b>${money(total)}</b></div>`;
    box.innerHTML = html;
}
function removeSelected(idx) {
    const items = getSelected();
    items.splice(idx, 1);
    setSelected(items);
    renderSelected();
    syncChecks();
}
function clearSelected() {
    setSelected([]);
    renderSelected();
    syncChecks();
}
function toggleSelect(id, code, retail) {
    let items = getSelected();
    const exists = items.findIndex(x => String(x.id) === String(id));

    if (exists >= 0) items.splice(exists, 1);
    else items.push({id:id, code:code, retail:Number(retail || 0)});

    setSelected(items);
    renderSelected();
    syncChecks();
}
function syncChecks() {
    const items = getSelected();
    document.querySelectorAll(".item-check").forEach(chk => {
        chk.checked = items.some(x => String(x.id) === String(chk.dataset.id));
    });
}
function copyText(text) {
    navigator.clipboard.writeText(text).then(() => alert("복사되었습니다."));
}
function copySingle(id) {
    const text = document.getElementById("deposit" + id).value;
    copyText(text);
}
function copyBundle() {
    const items = getSelected();
    if (!items.length) {
        alert("선택된 상품이 없습니다.");
        return;
    }

    const lines = items.map(it => `${it.code} ${money(it.retail)}`);
    const total = items.reduce((sum, it) => sum + Number(it.retail || 0), 0);

    let template = document.getElementById("bundleTemplate").value;
    template = template.replace(/입금금액\\s*:\\s*.*/g, "입금금액 : " + money(total));

    const finalText = lines.join("\\n") + "\\n\\n" + template;
    copyText(finalText);
}
document.addEventListener("DOMContentLoaded", () => {
    renderSelected();
    syncChecks();
});
</script>
</head>
<body>

<h2>상품 검색</h2>
<a class="admin-link" href="/admin">관리자 페이지</a>

<form method="get" class="search">
    <input name="q" placeholder="브랜드 / 코드 / 거래처 검색" value="{{ q }}">
    <button>검색</button>
</form>

<div class="notice">
검색 캐시: {{ cache_count }}건 / 검색결과: {{ rows|length }}건
</div>

<div id="selectedWrap" class="selected-box" style="display:none;">
    <b>선택 상품</b>
    <div id="selectedList"></div>
    <button type="button" onclick="copyBundle()" style="margin-top:8px;">묶음 입금요청 복사</button>
    <button type="button" onclick="clearSelected()" style="margin-top:8px;background:#777;">선택 초기화</button>
</div>

<textarea id="bundleTemplate" style="display:none;">{{ bundle_template }}</textarea>

{% for r in rows %}
<div class="card" style="position:relative;">
    <label class="check-area">
        <input
            type="checkbox"
            class="item-check"
            data-id="{{ r.id }}"
            onchange="toggleSelect('{{ r.id }}', '{{ r.brand_code }} {{ r.serial }}', '{{ r.retail or 0 }}')"
        >
        선택
    </label>

    <div class="code">{{ r.brand_code }} {{ r.serial }}</div>
    <div class="row">브랜드: {{ r.brand_name }}</div>
    <div class="row">거래처: {{ r.client }}</div>
    <div class="row">구분: {{ r.division or "" }}</div>
    <div class="row">도매가: {{ "{:,}".format(r.wholesale or 0) }}원</div>
    <div class="row">소매가: {{ "{:,}".format(r.retail or 0) }}원</div>
    <div class="row small">등록일: {{ r.created_at }}</div>

    <textarea id="deposit{{ r.id }}" style="display:none;">{{ r.deposit_message }}</textarea>
    <button onclick="copySingle('{{ r.id }}')">입금요청 복사</button>
</div>
{% endfor %}

</body>
</html>
"""


ADMIN_LOGIN_HTML = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>관리자 로그인</title>
""" + BASE_STYLE + """
</head>
<body>
<h2>관리자 로그인</h2>
<form method="post">
    <div class="box">
        <input type="password" name="password" placeholder="관리 비밀번호">
        <button>확인</button>
    </div>
</form>
<p><a href="/">검색화면으로</a></p>
</body>
</html>
"""


ADMIN_HOME_HTML = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>관리자</title>
""" + BASE_STYLE + """
</head>
<body>
<h2>관리자 페이지</h2>

<div class="box nav">
    <a class="btn" href="/admin/settings?password={{ password }}">계좌/입금문구</a>
    <a class="btn" href="/admin/brands?password={{ password }}">브랜드 관리</a>
    <a class="btn" href="/admin/clients?password={{ password }}">거래처 관리</a>
    <a class="btn" href="/admin/divisions?password={{ password }}">구분 관리</a>
    <a class="btn" href="/admin/rates?password={{ password }}">단가비율 관리</a>
    <a class="btn" href="/admin/items?password={{ password }}">상품 수정</a>
    <a class="btn" href="/admin/cache?password={{ password }}">검색캐시 재생성</a>
</div>

<div class="box">
    <div>검색 캐시: {{ cache_count }}건</div>
</div>

<p><a href="/">검색화면으로</a></p>
</body>
</html>
"""


SETTINGS_HTML = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>계좌/입금문구</title>
""" + BASE_STYLE + """
</head>
<body>
<h2>계좌 / 입금요청 관리</h2>

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
        <textarea name="deposit_message" style="height:230px;">{{ deposit_message }}</textarea>
    </div>

    <button name="save" value="1">저장/수정</button>
    <button name="delete" value="1" class="btn-red">삭제</button>
</form>

<p><a href="/admin?password={{ password }}">관리자 홈</a></p>
</body>
</html>
"""


MASTER_HTML = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
""" + BASE_STYLE + """
</head>
<body>
<h2>{{ title }}</h2>

<form method="post" class="box">
    <input type="hidden" name="password" value="{{ password }}">
    <input type="hidden" name="id" value="{{ edit.id if edit else '' }}">

    이름
    <input name="name" value="{{ edit.name if edit else '' }}">

    {% if table == 'brands' %}
    영문 2자리
    <input name="code" value="{{ edit.code if edit else '' }}">
    {% endif %}

    <button name="save" value="1">저장/수정</button>
    {% if edit %}
    <button name="delete" value="1" class="btn-red">삭제</button>
    {% endif %}
</form>

<form method="get" class="search">
    <input type="hidden" name="password" value="{{ password }}">
    <input name="q" placeholder="검색" value="{{ q }}">
    <button>검색</button>
</form>

{% if table == 'brands' %}
<form method="post" class="box">
    <input type="hidden" name="password" value="{{ password }}">
    <h3>브랜드 일괄등록</h3>
    <textarea name="bulk_text" style="height:180px;" placeholder="몽클레어 MC&#10;톰브라운 TB"></textarea>
    <button name="bulk" value="1">일괄등록/덮어쓰기</button>
</form>
{% endif %}

{% for r in rows %}
<div class="card">
    <b>{{ r.name }}</b>
    {% if table == 'brands' %}
    <div>코드: {{ r.code }}</div>
    {% endif %}
    <a class="btn btn-gray" href="/admin/{{ table }}?password={{ password }}&edit_id={{ r.id }}&q={{ q }}">수정</a>
</div>
{% endfor %}

<p><a href="/admin?password={{ password }}">관리자 홈</a></p>
</body>
</html>
"""


RATES_HTML = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>단가비율 관리</title>
""" + BASE_STYLE + """
</head>
<body>
<h2>단가비율 관리</h2>

<form method="post" class="box">
    <input type="hidden" name="password" value="{{ password }}">
    <input type="hidden" name="id" value="{{ edit.id if edit else '' }}">

    이름
    <input name="name" value="{{ edit.name if edit else '' }}" placeholder="1.5배">

    실제 값
    <input name="value" value="{{ edit.value if edit else '' }}" placeholder="1.5">

    <button name="save" value="1">저장/수정</button>
    {% if edit %}
    <button name="delete" value="1" class="btn-red">삭제</button>
    {% endif %}
</form>

{% for r in rows %}
<div class="card">
    <b>{{ r.name }}</b>
    <div>값: {{ r.value }}</div>
    <a class="btn btn-gray" href="/admin/rates?password={{ password }}&edit_id={{ r.id }}">수정</a>
</div>
{% endfor %}

<p><a href="/admin?password={{ password }}">관리자 홈</a></p>
</body>
</html>
"""


ITEMS_ADMIN_HTML = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>상품 수정</title>
""" + BASE_STYLE + """
</head>
<body>
<h2>상품 수정</h2>

<form method="get" class="search">
    <input type="hidden" name="password" value="{{ password }}">
    <input name="q" placeholder="코드 / 브랜드 / 거래처 검색" value="{{ q }}">
    <button>검색</button>
</form>

{% for r in rows %}
<div class="card">
    <div class="code">{{ r.brand_code }} {{ r.serial }}</div>
    <div>브랜드: {{ r.brand_name }}</div>
    <div>거래처: {{ r.client }}</div>
    <div>구분: {{ r.division }}</div>
    <div>도매가: {{ "{:,}".format(r.wholesale or 0) }}</div>
    <div>소매가: {{ "{:,}".format(r.retail or 0) }}</div>
    <a class="btn" href="/admin/item/{{ r.id }}?password={{ password }}">수정</a>
</div>
{% endfor %}

<p><a href="/admin?password={{ password }}">관리자 홈</a></p>
</body>
</html>
"""


ITEM_EDIT_HTML = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>상품 수정</title>
""" + BASE_STYLE + """
</head>
<body>
<h2>상품 수정</h2>

<form method="post" class="box">
    <input type="hidden" name="password" value="{{ password }}">

    브랜드명
    <input name="brand_name" value="{{ item.brand_name or '' }}">

    브랜드코드
    <input name="brand_code" value="{{ item.brand_code or '' }}">

    숫자코드
    <input name="serial" value="{{ item.serial or '' }}">

    거래처
    <input name="client" value="{{ item.client or '' }}">

    구분
    <input name="division" value="{{ item.division or '' }}">

    도매가
    <input name="wholesale" value="{{ item.wholesale or 0 }}">

    소매가
    <input name="retail" value="{{ item.retail or 0 }}">

    <button name="save" value="1">저장/수정</button>
    <button name="delete" value="1" class="btn-red">삭제</button>
</form>

<p><a href="/admin/items?password={{ password }}">상품 목록</a></p>
</body>
</html>
"""


CACHE_HTML = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>검색캐시</title>
""" + BASE_STYLE + """
</head>
<body>
<h2>검색캐시 재생성</h2>

<div class="box">
    <p>현재 검색 캐시: {{ cache_count }}건</p>
    <form method="post">
        <input type="hidden" name="password" value="{{ password }}">
        <button name="rebuild" value="1">검색캐시 재생성</button>
    </form>
</div>

{% if result %}
<div class="box">
    {{ result }}
</div>
{% endif %}

<p><a href="/admin?password={{ password }}">관리자 홈</a></p>
</body>
</html>
"""


@app.route("/")
def home():
    q = request.args.get("q", "").strip()
    cache_count = get_cache_count()

    conn = db()
    with conn.cursor() as cur:
        if cache_count > 0:
            if q:
                compact_q = normalize_search(q)
                cur.execute("""
                SELECT
                    item_id AS id,
                    brand_name,
                    brand_code,
                    serial,
                    client,
                    division,
                    wholesale,
                    retail,
                    created_at
                FROM pos_search_cache
                WHERE search_text LIKE %s
                   OR search_text LIKE %s
                   OR code_text LIKE %s
                   OR brand_code LIKE %s
                   OR serial LIKE %s
                ORDER BY created_at DESC
                LIMIT 100
                """, (
                    f"%{q}%",
                    f"%{compact_q}%",
                    f"%{q}%",
                    f"%{q}%",
                    f"%{q}%"
                ))
            else:
                cur.execute("""
                SELECT
                    item_id AS id,
                    brand_name,
                    brand_code,
                    serial,
                    client,
                    division,
                    wholesale,
                    retail,
                    created_at
                FROM pos_search_cache
                ORDER BY created_at DESC
                LIMIT 100
                """)
            rows = cur.fetchall()
        else:
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

    bundle_template = make_deposit_message_from_amount(0)

    return render_template_string(
        HTML,
        rows=rows,
        q=q,
        bundle_template=bundle_template,
        cache_count=cache_count
    )


@app.route("/admin", methods=["GET", "POST"])
def admin():
    password = request.values.get("password", "")

    if request.method == "POST":
        password = request.form.get("password", "")

    if password != ADMIN_PASSWORD:
        return render_template_string(ADMIN_LOGIN_HTML)

    return render_template_string(
        ADMIN_HOME_HTML,
        password=password,
        cache_count=get_cache_count()
    )


@app.route("/admin/settings", methods=["GET", "POST"])
def admin_settings():
    if not admin_ok():
        return redirect("/admin")

    password = request.values.get("password", "")

    if request.method == "POST":
        if request.form.get("save"):
            set_setting("account_holder", request.form.get("account_holder", ""))
            set_setting("bank_name", request.form.get("bank_name", ""))
            set_setting("account_number", request.form.get("account_number", ""))
            set_setting("deposit_message", request.form.get("deposit_message", ""))
        elif request.form.get("delete"):
            set_setting("account_holder", "")
            set_setting("bank_name", "")
            set_setting("account_number", "")
            set_setting("deposit_message", "")
        return redirect(f"/admin/settings?password={password}")

    return render_template_string(
        SETTINGS_HTML,
        password=password,
        account_holder=get_setting("account_holder", "조영민"),
        bank_name=get_setting("bank_name", "우리은행"),
        account_number=get_setting("account_number", "1005-104-856764"),
        deposit_message=get_setting("deposit_message", DEFAULT_DEPOSIT_MESSAGE)
    )


def master_page(table, title):
    if not admin_ok():
        return redirect("/admin")

    password = request.values.get("password", "")
    q = request.values.get("q", "").strip()
    edit_id = request.values.get("edit_id", "").strip()
    edit = None

    conn = db()

    with conn.cursor() as cur:
        if request.method == "POST":
            if request.form.get("bulk") and table == "brands":
                bulk_text = request.form.get("bulk_text", "")
                for raw in bulk_text.splitlines():
                    line = raw.strip()
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    code = parts[-1].strip().upper()
                    name = " ".join(parts[:-1]).strip()
                    if len(code) != 2:
                        continue

                    cur.execute("SELECT id FROM brands WHERE code=%s", (code,))
                    row = cur.fetchone()
                    if row:
                        cur.execute("UPDATE brands SET name=%s WHERE id=%s", (name, row["id"]))
                    else:
                        cur.execute("SELECT id FROM brands WHERE name=%s", (name,))
                        row2 = cur.fetchone()
                        if row2:
                            cur.execute("UPDATE brands SET code=%s WHERE id=%s", (code, row2["id"]))
                        else:
                            cur.execute("INSERT INTO brands(name, code) VALUES(%s, %s)", (name, code))

                    cur.execute("UPDATE items SET brand_name=%s WHERE brand_code=%s", (name, code))

                conn.commit()
                conn.close()
                return redirect(f"/admin/{table}?password={password}")

            row_id = request.form.get("id", "").strip()
            name = request.form.get("name", "").strip()

            if request.form.get("delete") and row_id:
                cur.execute(f"DELETE FROM {table} WHERE id=%s", (row_id,))
                conn.commit()
                conn.close()
                return redirect(f"/admin/{table}?password={password}")

            if request.form.get("save") and name:
                if table == "brands":
                    code = request.form.get("code", "").strip().upper()

                    if row_id:
                        cur.execute("UPDATE brands SET name=%s, code=%s WHERE id=%s", (name, code, row_id))
                    else:
                        cur.execute("""
                        INSERT INTO brands(name, code)
                        VALUES(%s, %s)
                        ON DUPLICATE KEY UPDATE name=%s, code=%s
                        """, (name, code, name, code))

                    cur.execute("UPDATE items SET brand_name=%s WHERE brand_code=%s", (name, code))
                else:
                    if row_id:
                        cur.execute(f"UPDATE {table} SET name=%s WHERE id=%s", (name, row_id))
                    else:
                        cur.execute(f"INSERT IGNORE INTO {table}(name) VALUES(%s)", (name,))

                conn.commit()
                conn.close()
                return redirect(f"/admin/{table}?password={password}")

        if edit_id:
            cur.execute(f"SELECT * FROM {table} WHERE id=%s", (edit_id,))
            edit = cur.fetchone()

        if q:
            if table == "brands":
                cur.execute("SELECT * FROM brands WHERE name LIKE %s OR code LIKE %s ORDER BY name LIMIT 200", (f"%{q}%", f"%{q}%"))
            else:
                cur.execute(f"SELECT * FROM {table} WHERE name LIKE %s ORDER BY name LIMIT 200", (f"%{q}%",))
        else:
            cur.execute(f"SELECT * FROM {table} ORDER BY name LIMIT 200")

        rows = cur.fetchall()

    conn.close()

    return render_template_string(
        MASTER_HTML,
        password=password,
        table=table,
        title=title,
        rows=rows,
        q=q,
        edit=edit
    )


@app.route("/admin/brands", methods=["GET", "POST"])
def admin_brands():
    return master_page("brands", "브랜드 관리")


@app.route("/admin/clients", methods=["GET", "POST"])
def admin_clients():
    return master_page("clients", "거래처 관리")


@app.route("/admin/divisions", methods=["GET", "POST"])
def admin_divisions():
    return master_page("divisions", "구분 관리")


@app.route("/admin/rates", methods=["GET", "POST"])
def admin_rates():
    if not admin_ok():
        return redirect("/admin")

    password = request.values.get("password", "")
    edit_id = request.values.get("edit_id", "").strip()
    edit = None

    conn = db()
    with conn.cursor() as cur:
        if request.method == "POST":
            row_id = request.form.get("id", "").strip()

            if request.form.get("delete") and row_id:
                cur.execute("DELETE FROM rates WHERE id=%s", (row_id,))
                conn.commit()
                conn.close()
                return redirect(f"/admin/rates?password={password}")

            if request.form.get("save"):
                name = request.form.get("name", "").strip()
                try:
                    value = float(request.form.get("value", "0"))
                except Exception:
                    value = 0

                if row_id:
                    cur.execute("UPDATE rates SET name=%s, value=%s WHERE id=%s", (name, value, row_id))
                else:
                    cur.execute("""
                    INSERT INTO rates(name, value)
                    VALUES(%s, %s)
                    ON DUPLICATE KEY UPDATE value=%s
                    """, (name, value, value))

                conn.commit()
                conn.close()
                return redirect(f"/admin/rates?password={password}")

        if edit_id:
            cur.execute("SELECT * FROM rates WHERE id=%s", (edit_id,))
            edit = cur.fetchone()

        cur.execute("SELECT * FROM rates ORDER BY id")
        rows = cur.fetchall()

    conn.close()

    return render_template_string(RATES_HTML, password=password, rows=rows, edit=edit)


@app.route("/admin/items")
def admin_items():
    if not admin_ok():
        return redirect("/admin")

    password = request.values.get("password", "")
    q = request.args.get("q", "").strip()

    conn = db()
    with conn.cursor() as cur:
        if q:
            compact_q = normalize_search(q)
            cur.execute("""
            SELECT
                item_id AS id,
                brand_name,
                brand_code,
                serial,
                client,
                division,
                wholesale,
                retail,
                created_at
            FROM pos_search_cache
            WHERE search_text LIKE %s
               OR search_text LIKE %s
               OR code_text LIKE %s
               OR brand_code LIKE %s
               OR serial LIKE %s
            ORDER BY created_at DESC
            LIMIT 100
            """, (f"%{q}%", f"%{compact_q}%", f"%{q}%", f"%{q}%", f"%{q}%"))
            rows = cur.fetchall()
        else:
            cur.execute("SELECT * FROM items ORDER BY id DESC LIMIT 100")
            rows = cur.fetchall()

    conn.close()

    return render_template_string(ITEMS_ADMIN_HTML, password=password, rows=rows, q=q)


@app.route("/admin/item/<int:item_id>", methods=["GET", "POST"])
def admin_item_edit(item_id):
    if not admin_ok():
        return redirect("/admin")

    password = request.values.get("password", "")

    conn = db()
    with conn.cursor() as cur:
        if request.method == "POST":
            if request.form.get("delete"):
                cur.execute("DELETE FROM items WHERE id=%s", (item_id,))
                cur.execute("DELETE FROM pos_search_cache WHERE item_id=%s", (item_id,))
                conn.commit()
                conn.close()
                return redirect(f"/admin/items?password={password}")

            if request.form.get("save"):
                brand_name = request.form.get("brand_name", "").strip()
                brand_code = request.form.get("brand_code", "").strip().upper()
                serial = request.form.get("serial", "").strip()
                client = request.form.get("client", "").strip()
                division = request.form.get("division", "").strip()

                try:
                    wholesale = int(str(request.form.get("wholesale", "0")).replace(",", ""))
                except Exception:
                    wholesale = 0

                try:
                    retail = int(str(request.form.get("retail", "0")).replace(",", ""))
                except Exception:
                    retail = 0

                cur.execute("""
                UPDATE items
                SET brand_name=%s,
                    brand_code=%s,
                    serial=%s,
                    client=%s,
                    division=%s,
                    wholesale=%s,
                    retail=%s
                WHERE id=%s
                """, (brand_name, brand_code, serial, client, division, wholesale, retail, item_id))

                cur.execute("INSERT IGNORE INTO clients(name) VALUES(%s)", (client,))
                cur.execute("INSERT IGNORE INTO divisions(name) VALUES(%s)", (division,))

                conn.commit()

                conn.close()
                rebuild_search_cache()
                return redirect(f"/admin/item/{item_id}?password={password}")

        cur.execute("SELECT * FROM items WHERE id=%s", (item_id,))
        item = cur.fetchone()

    conn.close()

    if not item:
        return "상품을 찾을 수 없습니다."

    return render_template_string(ITEM_EDIT_HTML, password=password, item=item)


@app.route("/admin/cache", methods=["GET", "POST"])
def admin_cache():
    if not admin_ok():
        return redirect("/admin")

    password = request.values.get("password", "")
    result = ""

    if request.method == "POST" and request.form.get("rebuild"):
        count = rebuild_search_cache()
        result = f"검색캐시 재생성 완료: {count}건"

    return render_template_string(
        CACHE_HTML,
        password=password,
        cache_count=get_cache_count(),
        result=result
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
