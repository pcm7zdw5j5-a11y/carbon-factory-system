from datetime import date

from app import create_app
from app.database import get_db
from tests.helpers import create_user, login, logout


def make_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "carbon_factory.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )


def create_month_order(client, order_no, source="淘宝", status="已完成", customer="统计客户"):
    response = client.post(
        "/orders/new",
        data={
            "order_no": order_no,
            "source": source,
            "customer_name": customer,
            "customer_contact": "13855556666",
            "product_name": "统计测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "2",
            "board_count": "1",
            "delivery_date": "2026-05-30",
            "processing_requirements": "倒角",
            "notes": "月度打印测试",
            "status": status,
            "final_quote": "1000",
            "labor_cost": "100",
            "machine_cost": "80",
            "packaging_cost": "30",
            "shipping_cost": "20",
            "platform_fee": "25",
            "other_cost": "10",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_statistics_page_contains_print_report_and_order_details(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    create_month_order(client, "CF-PRINT-001", "淘宝", "已完成", "张三")
    create_month_order(client, "CF-PRINT-002", "微信", "加工中", "李四")

    today = date.today()
    response = client.get(f"/statistics?year={today.year}&month={today.month}")
    page = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "打印本月报表" in page
    assert "导出为 PDF" in page
    assert "window.print()" in page
    assert 'class="print-area monthly-report"' in page
    assert "碳纤维工厂月度经营统计报表" in page
    assert f"{today.year}年{today.month}月" in page
    assert "打印时间" in page
    assert "订单总数" in page
    assert "板材总成本" in page
    assert "人工成本总额" in page
    assert "机器成本总额" in page
    assert "包装成本总额" in page
    assert "快递成本总额" in page
    assert "平台手续费总额" in page
    assert "其他成本总额" in page
    assert "总利润" in page
    assert "平均毛利率" in page
    assert "淘宝销售额" in page
    assert "微信销售额" in page
    assert "线下销售额" in page
    assert "其他销售额" in page
    assert "待审核" in page
    assert "已取消" in page
    assert "明细订单表" in page
    assert "CF-PRINT-001" in page
    assert "CF-PRINT-002" in page
    assert "张三" in page
    assert "统计测试板" in page
    assert "summary-mobile-grid" in page
    assert "summary-mobile-card" in page


def test_statistics_print_permission_does_not_leak_to_sales(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "sales01", "sales123", "sales")
    login(client)
    create_month_order(client, "CF-PRINT-PERM")

    logout(client)
    login(client, "sales01", "sales123")
    response = client.get("/statistics")

    assert response.status_code == 403
    assert "碳纤维工厂月度经营统计报表".encode("utf-8") not in response.data
    assert "打印本月报表".encode("utf-8") not in response.data


def test_statistics_print_css_hides_navigation_and_preserves_tables():
    css = open("static/style.css", encoding="utf-8").read()

    assert "@media print" in css
    assert "@page" in css
    assert ".no-print" in css
    assert ".topbar" in css
    assert ".mobile-bottom-nav" in css
    assert ".print-area" in css
    assert "window.print" not in css
    assert "page-break-inside: avoid" in css or "break-inside: avoid" in css


def test_statistics_mobile_summary_uses_cards_and_print_keeps_table():
    css = open("static/style.css", encoding="utf-8").read()

    assert ".summary-mobile-grid" in css
    assert ".summary-mobile-card" in css
    assert ".summary-table" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css
    assert "overflow-wrap: anywhere" in css
    assert "@media print" in css
    assert ".summary-mobile-grid" in css and "display: none !important" in css
