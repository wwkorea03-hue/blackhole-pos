from flask import Flask, request, render_template_string
import pymysql
import os

app = Flask(__name__)

def db():
    return pymysql.connect(
        host=os.getenv("MYSQLHOST"),
        port=int(os.getenv("MYSQLPORT")),
        user=os.getenv("MYSQLUSER"),
        password=os.getenv("MYSQLPASSWORD"),
        database=os.getenv("MYSQLDATABASE"),
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
            shipping_fee INT,
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
<title>자료 검색</title>

<style>
body{
    font-family:Arial;
    padding:15px;
    background:#f4f4f4;
}

input{
    width:100%;
    padding:12px;
    font-size:16px;
    box-sizing:border-box;
}

button{
    width:100%;
    padding:12px;
    margin-top:8px;
    font-size:16px;
}

.card{
    background:white;
    padding:15px;
    border-radius:10px;
    margin-top:10px;
}

.code{
    font-size:22px;
    font-weight:bold;
}
</style>
</head>

<body>

<h2>상품 검색</h2>

<form>
<input name="q" placeholder="브랜드 / 코드 / 거래처 검색" value="{{q}}">
<button>검색</button>
</form>

{% for r in rows %}
<div class="card">
<div class="code">{{r.brand_code}} {{r.serial}}</div>
<div>{{r.brand_name}}</div>
<div>거래처 : {{r.client}}</div>
<div>도매가 : {{ "{:,}".format(r.wholesale) }}원</div>
<div>단가비율 : {{r.rate_name}}</div>
<div>배송비 : {{ "{:,}".format(r.shipping_fee) }}원</div>
<div>소매가 : {{ "{:,}".format(r.retail) }}원</div>
</div>
{% endfor %}

</body>
</html>
"""

@app.route("/")
def home():

    q = request.args.get("q", "")

    conn = db()

    with conn.cursor() as cur:

        if q:
            cur.execute("""
            SELECT * FROM items
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
            SELECT * FROM items
            ORDER BY id DESC
            LIMIT 100
            """)

        rows = cur.fetchall()

    conn.close()

    return render_template_string(
        HTML,
        rows=rows,
        q=q
    )

init_db()