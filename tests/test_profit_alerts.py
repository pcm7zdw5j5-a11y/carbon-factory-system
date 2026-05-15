from app import create_app
from app.database import get_db
from app.repositories import create_order
from tests.helpers import create_user, login, logout


def make_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "carbon_factory.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )


def seed_order(app, order_no, profit, margin_rate):
    final_quote = 1000
    total_cost = final_quote - profit
    with app.app_context():
        return create_order(
            {
                "order_no": order_no,
                "source": "淘宝",
                "customer_name": f"利润客户{order_no}",
                "customer_contact": "13800000000",
                "product_name": "碳纤维测试板",
                "material_type": "碳纤维板",
                "specification": "400×500",
                "thickness": "3mm",
                "quantity": 1,
                "board_count": 1,
                "delivery_date": "2026-05-20",
                "processing_requirements": "",
                "notes": "",
                "status": "已报价",
                "sale_unit_price": 0,
                "cost_unit_price": 0,
                "cutting_length": 0,
                "cutting_unit_price": 12,
                "hole_count": 0,
                "hole_unit_price": 2,
                "chamfer_count": 0,
                "chamfer_unit_price": 3,
                "polishing_fee": 0,
                "packaging_fee": 50,
                "shipping_fee": 0,
                "other_fee": 0,
                "is_urgent": 0,
                "urgent_rate": 0.2,
                "include_tax": 0,
                "tax_rate": 0.13,
                "material_quote": 0,
                "cutting_fee": 0,
                "hole_fee": 0,
                "chamfer_fee": 0,
                "quote_subtotal": final_quote,
                "urgent_fee": 0,
                "tax_fee": 0,
                "quote_total": final_quote,
                "final_quote": final_quote,
                "material_cost": total_cost,
                "labor_cost": 0,
                "machine_cost": 0,
                "packaging_cost": 0,
                "shipping_cost": 0,
                "platform_fee": 0,
                "other_cost": 0,
                "total_cost": total_cost,
                "profit": profit,
                "margin_rate": margin_rate,
            }
        )


def test_admin_sees_profit_alert_badges_on_order_list_and_detail(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    low_id = seed_order(app, "CF-PROFIT-LOW", 150, 15)
    seed_order(app, "CF-PROFIT-DANGER", 50, 5)
    seed_order(app, "CF-PROFIT-LOSS", -20, -2)
    login(client)

    list_page = client.get("/orders").data.decode("utf-8")
    detail_page = client.get(f"/orders/{low_id}").data.decode("utf-8")

    assert "低利润" in list_page
    assert "危险利润" in list_page
    assert "亏损订单" in list_page
    assert "data-profit-alert" in list_page
    assert "利润预警" in detail_page
    assert "低利润" in detail_page


def test_dashboard_shows_low_profit_order_count_for_admin(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    seed_order(app, "CF-PROFIT-COUNT-1", 150, 15)
    seed_order(app, "CF-PROFIT-COUNT-2", 50, 5)
    seed_order(app, "CF-PROFIT-COUNT-3", 300, 30)
    login(client)

    page = client.get("/").data.decode("utf-8")

    assert "低利润订单" in page
    assert "<strong class=\"danger-text\">2</strong>" in page


def test_sales_cannot_see_profit_alert_details_or_filter(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "sales01", "sales123", "sales")
    low_id = seed_order(app, "CF-PROFIT-SALES", 50, 5)

    login(client, "sales01", "sales123")
    list_page = client.get("/orders").data.decode("utf-8")
    detail_page = client.get(f"/orders/{low_id}").data.decode("utf-8")

    assert "低利润" not in list_page
    assert "危险利润" not in list_page
    assert "亏损订单" not in list_page
    assert "data-filter-profit" not in list_page
    assert "利润预警" not in detail_page


def test_finance_can_filter_profit_alert_orders(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "finance01", "finance123", "finance")
    seed_order(app, "CF-PROFIT-FINANCE", 150, 15)
    logout(client)
    login(client, "finance01", "finance123")

    page = client.get("/orders").data.decode("utf-8")
    script = open("static/js/order_filter.js", encoding="utf-8").read()

    assert "利润预警" in page
    assert "data-filter-profit" in page
    assert 'data-profit-alert="low"' in page
    assert "profitAlert" in script
