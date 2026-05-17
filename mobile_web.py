# ============================================================
# Blackhole CRM Mobile Web
# ============================================================
# 휴대폰 브라우저에서 CRM 데이터를 조회하는 모바일 웹 서버입니다.
#
# 기능:
# - 고객명/연락처 검색
# - 고객 상세 / 포인트 / 구매내역 조회
# - 최근 구매내역 전체 조회
# - 기간 필터: 이번주 / 이번달 / 최근2개월 / 최근3개월 / 전체
# - 진행상황 필터: 전체 / 배송중 / 출고완료 / 취소 등
# - 송장번호 확인
#
# 실행:
# pip install flask pymysql
# python mobile_web.py
#
# 접속:
# 같은 PC/같은 와이파이 기준
# http://PC_IP주소:8000
#
# 예:
# http://192.168.0.10:8000
# ============================================================

from flask import Flask, request, render_template_string, redirect, url_for
import pymysql
from urllib.parse import urlparse, unquote
from datetime import datetime

# 중요:
# Blackhole_POS / CRM에서 사용하는 Railway MySQL URL을 그대로 넣으세요.
RAILWAY_MYSQL_URL = "mysql://root:PFQuQeqwIaYpqAvwQhFlInPRxHMiFptw@yamanote.proxy.rlwy.net:34336/railway"

app = Flask(__name__)


def db():
    u = urlparse(RAILWAY_MYSQL_URL)

    return pymysql.connect(
        host=u.hostname,
        port=u.port or 3306,
        user=unquote(u.username or ""),
        password=unquote(u.password or ""),
        database=u.path.lstrip("/"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=8,
        read_timeout=20,
        write_timeout=20,
    )


def fetch_all(sql, params=None):
    conn = db()

    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    finally:
        conn.close()


def money(value):
    try:
        return f"{int(value or 0):,}"
    except Exception:
        return "0"


def period_where(period):
    if period == "이번주":
        return "o.order_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
    if period == "이번달":
        return "o.order_date >= DATE_FORMAT(CURDATE(), '%%Y-%%m-01')"
    if period == "최근2개월":
        return "o.order_date >= DATE_SUB(CURDATE(), INTERVAL 2 MONTH)"
    if period == "최근3개월":
        return "o.order_date >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)"
    return ""


BASE_CSS = """
<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans KR", sans-serif;
    color: #0f172a;
}

.header {
    position: sticky;
    top: 0;
    z-index: 10;
    background: #020617;
    color: white;
    padding: 14px 16px;
}

.header h1 {
    margin: 0;
    font-size: 18px;
}

.header p {
    margin: 4px 0 0;
    color: #cbd5e1;
    font-size: 12px;
}

.container {
    padding: 12px;
    max-width: 900px;
    margin: 0 auto;
}

.card {
    background: white;
    border-radius: 16px;
    padding: 14px;
    margin-bottom: 12px;
    box-shadow: 0 1px 5px rgba(15, 23, 42, 0.08);
}

.title {
    font-weight: 800;
    font-size: 17px;
    margin-bottom: 8px;
}

.sub {
    color: #64748b;
    font-size: 13px;
}

.row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

input, select {
    width: 100%;
    padding: 12px;
    border: 1px solid #cbd5e1;
    border-radius: 12px;
    font-size: 15px;
}

button, .btn {
    display: inline-block;
    border: 0;
    border-radius: 12px;
    padding: 11px 14px;
    background: #020617;
    color: white;
    text-decoration: none;
    font-size: 14px;
    font-weight: 700;
    text-align: center;
}

.btn-light {
    background: #e2e8f0;
    color: #0f172a;
}

.btn-blue {
    background: #1e40af;
}

.grid2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}

.grid3 {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8px;
}

.kpi {
    background: #f8fafc;
    border-radius: 14px;
    padding: 10px;
}

.kpi .label {
    color: #64748b;
    font-size: 12px;
}

.kpi .value {
    font-size: 16px;
    font-weight: 900;
    margin-top: 4px;
}

.list-item {
    border-top: 1px solid #e2e8f0;
    padding: 12px 0;
}

.list-item:first-child {
    border-top: 0;
}

.badge {
    display: inline-block;
    padding: 4px 8px;
    background: #e2e8f0;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
}

.badge-blue {
    background: #dbeafe;
    color: #1e40af;
}

.badge-red {
    background: #fee2e2;
    color: #991b1b;
}

.small {
    font-size: 12px;
    color: #64748b;
}

.nav {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-bottom: 12px;
}

.nav a {
    display: block;
}

@media (max-width: 480px) {
    .grid3 {
        grid-template-columns: 1fr;
    }
}
</style>
"""


def layout(title, content):
    return f"""
<!doctype html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    {BASE_CSS}
</head>
<body>
    <div class="header">
        <h1>Blackhole CRM Mobile</h1>
        <p>{title}</p>
    </div>
    <div class="container">
        <div class="nav">
            <a class="btn btn-light" href="/">고객검색</a>
            <a class="btn btn-light" href="/recent">최근구매내역</a>
        </div>
        {content}
    </div>
</body>
</html>
"""


@app.route("/")
def index():
    q = request.args.get("q", "").strip()

    rows = []

    if q:
        like = f"%{q}%"

        rows = fetch_all("""
        SELECT
            id,
            consult_type,
            name,
            phone,
            address
        FROM crm_customers
        WHERE name LIKE %s
           OR phone LIKE %s
           OR address LIKE %s
        ORDER BY id DESC
        LIMIT 100
        """, (like, like, like))

    items_html = ""

    if q and not rows:
        items_html = '<div class="card">검색 결과가 없습니다.</div>'

    for r in rows:
        items_html += f"""
        <div class="card">
            <div class="title">{r.get("name") or ""}</div>
            <div class="sub">{r.get("phone") or ""}</div>
            <div class="sub">{r.get("address") or ""}</div>
            <div style="margin-top:10px;">
                <span class="badge">{r.get("consult_type") or ""}</span>
            </div>
            <div style="margin-top:12px;">
                <a class="btn btn-blue" href="/customer/{r["id"]}">상세보기</a>
            </div>
        </div>
        """

    content = f"""
    <div class="card">
        <div class="title">고객 검색</div>
        <form method="get" action="/">
            <input name="q" value="{q}" placeholder="이름 / 연락처 / 주소 검색">
            <div style="margin-top:8px;">
                <button type="submit">검색</button>
            </div>
        </form>
    </div>
    {items_html}
    """

    return render_template_string(layout("고객 검색", content))


@app.route("/customer/<int:customer_id>")
def customer_detail(customer_id):
    customer_rows = fetch_all("""
    SELECT *
    FROM crm_customers
    WHERE id=%s
    """, (customer_id,))

    if not customer_rows:
        return render_template_string(layout("고객 없음", '<div class="card">고객을 찾을 수 없습니다.</div>'))

    customer = customer_rows[0]

    totals = fetch_all("""
    SELECT
        COALESCE(SUM(retail), 0) AS retail_sum,
        COALESCE(SUM(discount), 0) AS discount_sum,
        COALESCE(SUM(margin), 0) AS margin_sum,
        COALESCE(SUM(point), 0) AS point_sum,
        COUNT(*) AS order_count
    FROM crm_orders
    WHERE customer_id=%s
    """, (customer_id,))[0]

    orders = fetch_all("""
    SELECT *
    FROM crm_orders
    WHERE customer_id=%s
    ORDER BY id DESC
    LIMIT 200
    """, (customer_id,))

    order_html = ""

    if not orders:
        order_html = '<div class="card">구매내역이 없습니다.</div>'

    for o in orders:
        progress = o.get("progress_status") or ""

        badge_class = "badge-blue"
        if progress in ["취소", "반품"]:
            badge_class = "badge-red"

        invoice = f'{o.get("courier") or ""} {o.get("invoice_no") or ""}'.strip()

        order_html += f"""
        <div class="card">
            <div class="row" style="justify-content:space-between;">
                <div class="title">{o.get("product_code") or ""}</div>
                <span class="badge {badge_class}">{progress}</span>
            </div>
            <div><b>{o.get("product_name") or ""}</b></div>
            <div class="sub">{o.get("color") or ""} / {o.get("size") or ""}</div>
            <div class="grid3" style="margin-top:10px;">
                <div class="kpi"><div class="label">소매가</div><div class="value">{money(o.get("retail"))}원</div></div>
                <div class="kpi"><div class="label">마진</div><div class="value">{money(o.get("margin"))}원</div></div>
                <div class="kpi"><div class="label">포인트</div><div class="value">{money(o.get("point"))}P</div></div>
            </div>
            <div style="margin-top:10px;">
                <div class="small">주문일: {o.get("order_date") or ""}</div>
                <div class="small">입금상태: {o.get("payment_status") or ""}</div>
                <div class="small">대금결제: {o.get("vendor_payment") or ""}</div>
                <div class="small">입고일자: {o.get("inbound_date") or ""}</div>
                <div class="small">출고일자: {o.get("outbound_date") or ""}</div>
                <div class="small">송장번호: {invoice or "-"}</div>
            </div>
        </div>
        """

    content = f"""
    <div class="card">
        <div class="title">{customer.get("name") or ""}</div>
        <div class="sub">{customer.get("phone") or ""}</div>
        <div class="sub">{customer.get("address") or ""}</div>
        <div style="margin-top:10px;">
            <span class="badge">{customer.get("consult_type") or ""}</span>
        </div>
    </div>

    <div class="card">
        <div class="title">고객 요약</div>
        <div class="grid3">
            <div class="kpi"><div class="label">구매건수</div><div class="value">{money(totals.get("order_count"))}건</div></div>
            <div class="kpi"><div class="label">총구매금액</div><div class="value">{money(totals.get("retail_sum"))}원</div></div>
            <div class="kpi"><div class="label">포인트</div><div class="value">{money(totals.get("point_sum"))}P</div></div>
            <div class="kpi"><div class="label">할인</div><div class="value">{money(totals.get("discount_sum"))}원</div></div>
            <div class="kpi"><div class="label">마진</div><div class="value">{money(totals.get("margin_sum"))}원</div></div>
        </div>
    </div>

    <div class="title" style="margin:16px 4px 8px;">구매내역</div>
    {order_html}
    """

    return render_template_string(layout("고객 상세", content))


@app.route("/recent")
def recent_orders():
    period = request.args.get("period", "이번달")
    status = request.args.get("status", "전체")
    q = request.args.get("q", "").strip()

    where = []
    params = []

    pwhere = period_where(period)

    if pwhere:
        where.append(pwhere)

    if status != "전체":
        where.append("o.progress_status=%s")
        params.append(status)

    if q:
        like = f"%{q}%"

        where.append("""
        (
            c.name LIKE %s
            OR c.phone LIKE %s
            OR o.product_code LIKE %s
            OR o.product_name LIKE %s
            OR o.color LIKE %s
            OR o.size LIKE %s
            OR o.client LIKE %s
            OR o.invoice_no LIKE %s
        )
        """)

        params.extend([like, like, like, like, like, like, like, like])

    where_sql = ""

    if where:
        where_sql = "WHERE " + " AND ".join(where)

    rows = fetch_all(f"""
    SELECT
        o.*,
        c.name AS customer_name,
        c.phone AS customer_phone
    FROM crm_orders o
    LEFT JOIN crm_customers c
        ON o.customer_id=c.id
    {where_sql}
    ORDER BY o.id DESC
    LIMIT 300
    """, tuple(params))

    period_options = ["이번주", "이번달", "최근2개월", "최근3개월", "전체"]
    status_options = ["전체", "주문접수", "입고대기", "입고완료", "배송준비", "배송중", "출고완료", "취소", "교환", "반품"]

    period_html = "".join(
        f'<option value="{x}" {"selected" if x == period else ""}>{x}</option>'
        for x in period_options
    )

    status_html = "".join(
        f'<option value="{x}" {"selected" if x == status else ""}>{x}</option>'
        for x in status_options
    )

    list_html = ""

    if not rows:
        list_html = '<div class="card">최근 구매내역이 없습니다.</div>'

    for o in rows:
        progress = o.get("progress_status") or ""

        badge_class = "badge-blue"
        if progress in ["취소", "반품"]:
            badge_class = "badge-red"

        invoice = f'{o.get("courier") or ""} {o.get("invoice_no") or ""}'.strip()

        list_html += f"""
        <div class="card">
            <div class="row" style="justify-content:space-between;">
                <div>
                    <div class="title">{o.get("customer_name") or ""}</div>
                    <div class="sub">{o.get("customer_phone") or ""}</div>
                </div>
                <span class="badge {badge_class}">{progress}</span>
            </div>
            <div style="margin-top:8px;"><b>{o.get("product_code") or ""}</b> {o.get("product_name") or ""}</div>
            <div class="sub">{o.get("color") or ""} / {o.get("size") or ""}</div>
            <div class="grid2" style="margin-top:10px;">
                <div class="kpi"><div class="label">소매가</div><div class="value">{money(o.get("retail"))}원</div></div>
                <div class="kpi"><div class="label">송장번호</div><div class="value" style="font-size:13px;">{invoice or "-"}</div></div>
            </div>
            <div style="margin-top:10px;">
                <a class="btn btn-light" href="/customer/{o.get("customer_id")}">고객상세</a>
            </div>
        </div>
        """

    content = f"""
    <div class="card">
        <div class="title">최근 구매내역</div>
        <form method="get" action="/recent">
            <div class="grid2">
                <select name="period">{period_html}</select>
                <select name="status">{status_html}</select>
            </div>
            <div style="margin-top:8px;">
                <input name="q" value="{q}" placeholder="고객명 / 제품코드 / 송장번호 검색">
            </div>
            <div style="margin-top:8px;">
                <button type="submit">조회</button>
            </div>
        </form>
    </div>

    <div class="small" style="margin:0 4px 8px;">총 {len(rows)}건</div>
    {list_html}
    """

    return render_template_string(layout("최근 구매내역", content))


if __name__ == "__main__":
    print("Blackhole CRM Mobile Web 시작")
    print("PC에서 접속: http://127.0.0.1:8000")
    print("휴대폰에서 접속: http://PC_IP주소:8000")
    app.run(host="0.0.0.0", port=8000, debug=False)
