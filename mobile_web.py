import os
from datetime import datetime
from urllib.parse import urlparse, unquote

import pymysql
from flask import Flask, redirect, render_template_string, request, url_for

RAILWAY_MYSQL_URL = os.getenv(
    "RAILWAY_MYSQL_URL",
    "mysql://root:PFQuQeqwIaYpqAvwQhFlInPRxHMiFptw@yamanote.proxy.rlwy.net:34336/railway",
)

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


def execute(sql, params=None):
    conn = db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
    finally:
        conn.close()


def money(v):
    try:
        return f"{int(v or 0):,}"
    except Exception:
        return "0"


def to_int(v):
    try:
        return int(str(v or "0").replace(",", "").strip() or 0)
    except Exception:
        return 0


def today():
    return datetime.now().strftime("%Y-%m-%d")


def get_setting(key, default=""):
    try:
        rows = fetch_all("SELECT `value` FROM crm_settings WHERE `key`=%s", (key,))
        return rows[0]["value"] if rows else default
    except Exception:
        return default


def calc_point(retail):
    rate = float(get_setting("point_rate", "1") or 0)
    min_price = to_int(get_setting("point_min_price", "0") or 0)
    if retail < min_price:
        return 0
    return int(retail * (rate / 100))


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


CSS = """
<style>
*{box-sizing:border-box}body{margin:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",sans-serif;color:#0f172a}
.header{position:sticky;top:0;z-index:10;background:#020617;color:white;padding:14px 16px}.header h1{margin:0;font-size:18px}.header p{margin:4px 0 0;color:#cbd5e1;font-size:12px}
.container{padding:12px;max-width:920px;margin:0 auto}.card{background:white;border-radius:16px;padding:14px;margin-bottom:12px;box-shadow:0 1px 5px rgba(15,23,42,.08)}
.title{font-weight:800;font-size:17px;margin-bottom:8px}.sub{color:#64748b;font-size:13px}.small{font-size:12px;color:#64748b}.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
input,select,textarea{width:100%;padding:12px;border:1px solid #cbd5e1;border-radius:12px;font-size:15px}button,.btn{display:inline-block;border:0;border-radius:12px;padding:11px 14px;background:#020617;color:white;text-decoration:none;font-size:14px;font-weight:700;text-align:center}
.btn-light{background:#e2e8f0;color:#0f172a}.btn-blue{background:#1e40af}.btn-green{background:#047857}.btn-red{background:#991b1b}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:8px}.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
.kpi{background:#f8fafc;border-radius:14px;padding:10px}.kpi .label{color:#64748b;font-size:12px}.kpi .value{font-size:16px;font-weight:900;margin-top:4px}
.badge{display:inline-block;padding:4px 8px;background:#e2e8f0;border-radius:999px;font-size:12px;font-weight:700}.badge-blue{background:#dbeafe;color:#1e40af}.badge-red{background:#fee2e2;color:#991b1b}
.nav{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}.product-box{border:1px solid #e2e8f0;border-radius:14px;padding:12px;margin-bottom:8px}.fixed-bottom{position:sticky;bottom:0;background:#f1f5f9;padding:10px 0}
@media(max-width:520px){.grid2,.grid3{grid-template-columns:1fr}}
</style>
"""


def layout(title, content):
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>{CSS}</head>
<body><div class="header"><h1>Blackhole CRM Mobile</h1><p>{title}</p></div><div class="container"><div class="nav"><a class="btn btn-light" href="/">고객검색</a><a class="btn btn-light" href="/recent">최근구매내역</a></div>{content}</div></body></html>"""


@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    rows = []
    if q:
        like = f"%{q}%"
        rows = fetch_all(
            """
            SELECT id, consult_type, name, phone, address
            FROM crm_customers
            WHERE name LIKE %s OR phone LIKE %s OR address LIKE %s
            ORDER BY id DESC LIMIT 100
            """,
            (like, like, like),
        )

    html = f"""
    <div class="card"><div class="title">고객 검색</div>
    <form method="get"><input name="q" value="{q}" placeholder="이름 / 연락처 / 주소 검색"><div style="margin-top:8px"><button>검색</button></div></form></div>
    """
    if q and not rows:
        html += '<div class="card">검색 결과가 없습니다.</div>'
    for r in rows:
        html += f"""
        <div class="card"><div class="title">{r.get("name") or ""}</div><div class="sub">{r.get("phone") or ""}</div><div class="sub">{r.get("address") or ""}</div>
        <div style="margin-top:10px"><span class="badge">{r.get("consult_type") or ""}</span></div>
        <div class="row" style="margin-top:12px"><a class="btn btn-blue" href="/customer/{r["id"]}">상세보기</a><a class="btn btn-green" href="/customer/{r["id"]}/add-order">구매추가</a></div></div>
        """
    return render_template_string(layout("고객 검색", html))


@app.route("/customer/<int:customer_id>")
def customer_detail(customer_id):
    rows = fetch_all("SELECT * FROM crm_customers WHERE id=%s", (customer_id,))
    if not rows:
        return render_template_string(layout("고객 없음", '<div class="card">고객을 찾을 수 없습니다.</div>'))
    c = rows[0]
    totals = fetch_all(
        """
        SELECT COALESCE(SUM(retail),0) retail_sum, COALESCE(SUM(discount),0) discount_sum,
               COALESCE(SUM(margin),0) margin_sum, COALESCE(SUM(point),0) point_sum, COUNT(*) order_count
        FROM crm_orders WHERE customer_id=%s
        """,
        (customer_id,),
    )[0]
    orders = fetch_all("SELECT * FROM crm_orders WHERE customer_id=%s ORDER BY id DESC LIMIT 200", (customer_id,))

    order_html = ""
    for o in orders:
        progress = o.get("progress_status") or ""
        badge = "badge-red" if progress in ["취소", "반품"] else "badge-blue"
        invoice = f'{o.get("courier") or ""} {o.get("invoice_no") or ""}'.strip()
        order_html += f"""
        <div class="card"><div class="row" style="justify-content:space-between"><div class="title">{o.get("product_code") or ""}</div><span class="badge {badge}">{progress}</span></div>
        <div><b>{o.get("product_name") or ""}</b></div><div class="sub">{o.get("color") or ""} / {o.get("size") or ""}</div>
        <div class="grid3" style="margin-top:10px"><div class="kpi"><div class="label">소매가</div><div class="value">{money(o.get("retail"))}원</div></div><div class="kpi"><div class="label">마진</div><div class="value">{money(o.get("margin"))}원</div></div><div class="kpi"><div class="label">포인트</div><div class="value">{money(o.get("point"))}P</div></div></div>
        <div style="margin-top:10px"><div class="small">주문일: {o.get("order_date") or ""}</div><div class="small">입금상태: {o.get("payment_status") or ""}</div><div class="small">대금결제: {o.get("vendor_payment") or ""}</div><div class="small">입고일자: {o.get("inbound_date") or ""}</div><div class="small">출고일자: {o.get("outbound_date") or ""}</div><div class="small">송장번호: {invoice or "-"}</div></div></div>
        """
    if not order_html:
        order_html = '<div class="card">구매내역이 없습니다.</div>'

    html = f"""
    <div class="card"><div class="title">{c.get("name") or ""}</div><div class="sub">{c.get("phone") or ""}</div><div class="sub">{c.get("address") or ""}</div>
    <div style="margin-top:10px"><span class="badge">{c.get("consult_type") or ""}</span></div>
    <div style="margin-top:12px"><a class="btn btn-green" href="/customer/{customer_id}/add-order">구매내역 추가</a></div></div>
    <div class="card"><div class="title">고객 요약</div><div class="grid3">
    <div class="kpi"><div class="label">구매건수</div><div class="value">{money(totals.get("order_count"))}건</div></div>
    <div class="kpi"><div class="label">총구매금액</div><div class="value">{money(totals.get("retail_sum"))}원</div></div>
    <div class="kpi"><div class="label">포인트</div><div class="value">{money(totals.get("point_sum"))}P</div></div>
    <div class="kpi"><div class="label">할인</div><div class="value">{money(totals.get("discount_sum"))}원</div></div>
    <div class="kpi"><div class="label">마진</div><div class="value">{money(totals.get("margin_sum"))}원</div></div>
    </div></div><div class="title" style="margin:16px 4px 8px">구매내역</div>{order_html}
    """
    return render_template_string(layout("고객 상세", html))


@app.route("/customer/<int:customer_id>/add-order", methods=["GET", "POST"])
def add_order(customer_id):
    customers = fetch_all("SELECT * FROM crm_customers WHERE id=%s", (customer_id,))
    if not customers:
        return render_template_string(layout("고객 없음", '<div class="card">고객을 찾을 수 없습니다.</div>'))
    c = customers[0]

    if request.method == "POST":
        pos_item_id = to_int(request.form.get("pos_item_id"))
        order_date = request.form.get("order_date") or today()
        color = request.form.get("color", "").strip()
        size = request.form.get("size", "").strip()
        shipping_fee = to_int(request.form.get("shipping_fee"))
        discount = to_int(request.form.get("discount"))
        items = fetch_all(
            """
            SELECT id, brand_name, brand_code, serial, client, wholesale, retail,
                   CONCAT(brand_code, ' ', serial) product_code
            FROM items WHERE id=%s
            """,
            (pos_item_id,),
        )
        if not items:
            return render_template_string(layout("상품 오류", '<div class="card">선택한 상품을 찾을 수 없습니다.</div>'))
        item = items[0]
        retail = to_int(item.get("retail"))
        wholesale = to_int(item.get("wholesale"))
        margin = retail - wholesale - shipping_fee - discount
        point = calc_point(retail)
        execute(
            """
            INSERT INTO crm_orders (
                customer_id, order_date, pos_item_id, product_code, product_name, color, size,
                retail, wholesale, shipping_fee, discount, margin, point, client,
                payment_status, vendor_payment, progress_status, inbound_date, outbound_date, courier, invoice_no
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'입금대기','미결제','주문접수',NULL,NULL,'','')
            """,
            (
                customer_id,
                order_date,
                item["id"],
                item["product_code"],
                item.get("brand_name") or "",
                color,
                size,
                retail,
                wholesale,
                shipping_fee,
                discount,
                margin,
                point,
                item.get("client") or "",
            ),
        )
        return redirect(url_for("customer_detail", customer_id=customer_id))

    q = request.args.get("q", "").strip()
    selected_id = to_int(request.args.get("item_id"))
    selected = None
    products = []
    if selected_id:
        rows = fetch_all(
            """
            SELECT id, brand_name, brand_code, serial, client, wholesale, retail,
                   CONCAT(brand_code, ' ', serial) product_code
            FROM items WHERE id=%s
            """,
            (selected_id,),
        )
        selected = rows[0] if rows else None

    if q:
        like = f"%{q}%"
        products = fetch_all(
            """
            SELECT id, brand_name, brand_code, serial, client, wholesale, retail,
                   CONCAT(brand_code, ' ', serial) product_code
            FROM items
            WHERE CONCAT(brand_code, ' ', serial) LIKE %s OR brand_code LIKE %s OR serial LIKE %s OR brand_name LIKE %s OR client LIKE %s
            ORDER BY id DESC LIMIT 80
            """,
            (like, like, like, like, like),
        )
    elif not selected:
        products = fetch_all(
            """
            SELECT id, brand_name, brand_code, serial, client, wholesale, retail,
                   CONCAT(brand_code, ' ', serial) product_code
            FROM items ORDER BY id DESC LIMIT 30
            """
        )

    selected_html = ""
    if selected:
        retail = to_int(selected.get("retail"))
        wholesale = to_int(selected.get("wholesale"))
        selected_html = f"""
        <div class="card"><div class="title">선택 상품</div><div><b>{selected.get("product_code") or ""}</b></div><div>{selected.get("brand_name") or ""}</div><div class="sub">거래처: {selected.get("client") or ""}</div>
        <div class="grid3" style="margin-top:10px"><div class="kpi"><div class="label">소매가</div><div class="value">{money(retail)}원</div></div><div class="kpi"><div class="label">도매가</div><div class="value">{money(wholesale)}원</div></div><div class="kpi"><div class="label">예상포인트</div><div class="value">{money(calc_point(retail))}P</div></div></div></div>
        <div class="card"><div class="title">구매 입력</div><form method="post"><input type="hidden" name="pos_item_id" value="{selected["id"]}">
        <label class="small">날짜</label><input name="order_date" value="{today()}" placeholder="YYYY-MM-DD">
        <div class="grid2" style="margin-top:8px"><div><label class="small">색상</label><input name="color" placeholder="예: 블랙"></div><div><label class="small">사이즈</label><input name="size" placeholder="예: M"></div></div>
        <div class="grid2" style="margin-top:8px"><div><label class="small">배송비</label><input name="shipping_fee" value="0" inputmode="numeric"></div><div><label class="small">할인</label><input name="discount" value="0" inputmode="numeric"></div></div>
        <div class="fixed-bottom"><button type="submit" class="btn-green" style="width:100%">구매내역 저장</button></div></form></div>
        """

    product_html = ""
    if products:
        product_html = '<div class="card"><div class="title">상품 검색 결과</div>'
        for p in products:
            product_html += f"""
            <div class="product-box"><div><b>{p.get("product_code") or ""}</b></div><div>{p.get("brand_name") or ""}</div><div class="sub">거래처: {p.get("client") or ""}</div>
            <div class="grid2" style="margin-top:8px"><div class="kpi"><div class="label">소매가</div><div class="value">{money(p.get("retail"))}원</div></div><div class="kpi"><div class="label">도매가</div><div class="value">{money(p.get("wholesale"))}원</div></div></div>
            <div style="margin-top:8px"><a class="btn btn-blue" href="/customer/{customer_id}/add-order?item_id={p["id"]}&q={q}">이 상품 선택</a></div></div>
            """
        product_html += "</div>"

    html = f"""
    <div class="card"><div class="title">{c.get("name") or ""} 고객 구매내역 추가</div><div class="sub">{c.get("phone") or ""}</div><div style="margin-top:10px"><a class="btn btn-light" href="/customer/{customer_id}">고객 상세로 돌아가기</a></div></div>
    <div class="card"><div class="title">POS 상품 검색</div><form method="get"><input name="q" value="{q}" placeholder="제품코드 예: TB 32768 / 브랜드명 / 거래처 검색"><div style="margin-top:8px"><button>상품 검색</button></div></form></div>
    {selected_html}{product_html}
    """
    return render_template_string(layout("구매내역 추가", html))


@app.route("/recent")
def recent_orders():
    period = request.args.get("period", "이번달")
    status = request.args.get("status", "전체")
    q = request.args.get("q", "").strip()
    where, params = [], []
    pw = period_where(period)
    if pw:
        where.append(pw)
    if status != "전체":
        where.append("o.progress_status=%s")
        params.append(status)
    if q:
        like = f"%{q}%"
        where.append("(c.name LIKE %s OR c.phone LIKE %s OR o.product_code LIKE %s OR o.product_name LIKE %s OR o.color LIKE %s OR o.size LIKE %s OR o.client LIKE %s OR o.invoice_no LIKE %s)")
        params.extend([like, like, like, like, like, like, like, like])
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    rows = fetch_all(
        f"""
        SELECT o.*, c.name customer_name, c.phone customer_phone
        FROM crm_orders o LEFT JOIN crm_customers c ON o.customer_id=c.id
        {where_sql}
        ORDER BY o.id DESC LIMIT 300
        """,
        tuple(params),
    )
    period_options = ["이번주", "이번달", "최근2개월", "최근3개월", "전체"]
    status_options = ["전체", "주문접수", "입고대기", "입고완료", "배송준비", "배송중", "출고완료", "취소", "교환", "반품"]
    period_html = "".join(f'<option value="{x}" {"selected" if x == period else ""}>{x}</option>' for x in period_options)
    status_html = "".join(f'<option value="{x}" {"selected" if x == status else ""}>{x}</option>' for x in status_options)
    list_html = ""
    for o in rows:
        progress = o.get("progress_status") or ""
        badge = "badge-red" if progress in ["취소", "반품"] else "badge-blue"
        invoice = f'{o.get("courier") or ""} {o.get("invoice_no") or ""}'.strip()
        list_html += f"""
        <div class="card"><div class="row" style="justify-content:space-between"><div><div class="title">{o.get("customer_name") or ""}</div><div class="sub">{o.get("customer_phone") or ""}</div></div><span class="badge {badge}">{progress}</span></div>
        <div style="margin-top:8px"><b>{o.get("product_code") or ""}</b> {o.get("product_name") or ""}</div><div class="sub">{o.get("color") or ""} / {o.get("size") or ""}</div>
        <div class="grid2" style="margin-top:10px"><div class="kpi"><div class="label">소매가</div><div class="value">{money(o.get("retail"))}원</div></div><div class="kpi"><div class="label">송장번호</div><div class="value" style="font-size:13px">{invoice or "-"}</div></div></div>
        <div class="row" style="margin-top:10px"><a class="btn btn-light" href="/customer/{o.get("customer_id")}">고객상세</a><a class="btn btn-green" href="/customer/{o.get("customer_id")}/add-order">구매추가</a></div></div>
        """
    if not list_html:
        list_html = '<div class="card">최근 구매내역이 없습니다.</div>'
    html = f"""
    <div class="card"><div class="title">최근 구매내역</div><form method="get"><div class="grid2"><select name="period">{period_html}</select><select name="status">{status_html}</select></div>
    <div style="margin-top:8px"><input name="q" value="{q}" placeholder="고객명 / 제품코드 / 송장번호 검색"></div><div style="margin-top:8px"><button>조회</button></div></form></div>
    <div class="small" style="margin:0 4px 8px">총 {len(rows)}건</div>{list_html}
    """
    return render_template_string(layout("최근 구매내역", html))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
