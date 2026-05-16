import os
import pymysql
from flask import Flask, request, render_template_string

app = Flask(__name__)


def env(name, default=None):
    return os.getenv(name) or os.getenv(name.replace("_", "")) or default


def db():
    return pymysql.connect(
        host=env("MYSQLHOST"),
        port=int(env("MYSQLPORT", 3306)),
        user=env("MYSQLUSER"),
        password=env("MYSQLPASSWORD"),
        database=env("MYSQLDATABASE"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )


def init_db():
    conn = db()
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            brand_name VARCHAR(255),
            brand_code VARCHAR(20),
            serial VARCHAR(20),
            client VARCHAR(255),
            wholesale INT,
            rate_name VARCHAR(100),
            rate_value FLOAT,
            shipping_fee INT DEFAULT 4000,
            retail INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
    conn.commit()
    conn.close()


HTML = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>상품 검색</title>
<style>
body {
    font-family: Arial, sans-serif;
    background: #f4f4f4;
    padding: 14px;
}
h2 {
    margin-top: 0;
}
.search-box {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
}
input {
    flex: 1;
    padding: 12px;
    font-size: 16px;
    box-sizing: border-box;
}
button {
    padding: 12px;
    font-size: 16px;
}
.card {
    background: white;
    padding: 14px;
    border-radius: 10px;
    margin-bottom: 10px;
    box-shadow: 0 1px 4px #ccc;
}
.code {
    font-size: 22px;
    font-weight: bold;
    margin-bottom: 6px;
}
.row {
    margin: 4px 0;
}
.empty {
    background: white;
    padding: 18px;
    border-radius: 10px;
    text-align: center;
    color: #666;
}
</style>
</head>
<body>

<h2>상품 검색</h2>

<form method="get" class="search-box">
    <input name="q" placeholder="브랜드 / 코드 / 거래처 검색" value="{{ q }}">
    <button>검색</button>
</form>

{% if rows %}
    {% for r in rows %}
    <div class="card">
        <div class="code">{{ r.brand_code }} {{ r.serial }}</div>
        <div class="row">브랜드: {{ r.brand_name }}</div>
        <div class="row">거래처: {{ r.client }}</div>
        <div class="row">도매가: {{ "{:,}".format(r.wholesale or 0) }}원</div>
        <div class="row">단가비율: {{ r.rate_name }}</div>
        <div class="row">배송비: {{ "{:,}".format(r.shipping_fee or 0) }}원</div>
        <div class="row">소매가: {{ "{:,}".format(r.retail or 0) }}원</div>
        <div class="row">등록일: {{ r.created_at }}</div>
    </div>
    {% endfor %}
{% else %}
    <div class="empty">검색 결과가 없습니다.</div>
{% endif %}

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
                ORDER BY id DESC
            """, (
                f"%{q}%",
                f"%{q}%",
                f"%{q}%",
                f"%{q}%"
            ))
        else:
            cur.execute("""
                SELECT *
                FROM items
                ORDER BY id DESC
                LIMIT 100
            """)

        rows = cur.fetchall()

    conn.close()

    return render_template_string(HTML, rows=rows, q=q)


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