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


def seed_order(app, order_no, status, delivery_date="2026-05-14", updated_at="2026-05-14 09:00:00"):
    with app.app_context():
        order_id = create_order(
            {
                "order_no": order_no,
                "source": "淘宝",
                "customer_name": f"待办客户{order_no}",
                "customer_contact": "13800000000",
                "product_name": "待办测试板",
                "material_type": "碳纤维板",
                "specification": "400×500",
                "thickness": "3mm",
                "quantity": 1,
                "board_count": 1,
                "delivery_date": delivery_date,
                "processing_requirements": "",
                "notes": "",
                "status": status,
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
                "quote_subtotal": 500,
                "urgent_fee": 0,
                "tax_fee": 0,
                "quote_total": 500,
                "final_quote": 500,
                "material_cost": 250,
                "labor_cost": 0,
                "machine_cost": 0,
                "packaging_cost": 0,
                "shipping_cost": 0,
                "platform_fee": 0,
                "other_cost": 0,
                "total_cost": 250,
                "profit": 250,
                "margin_rate": 50,
            }
        )
        db = get_db()
        db.execute("UPDATE orders SET updated_at = ? WHERE id = ?", (updated_at, order_id))
        db.commit()
        return order_id


def test_admin_dashboard_shows_all_todo_groups(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    seed_order(app, "CF-TODO-DUE", "已报价", "2026-05-14")
    seed_order(app, "CF-TODO-QUOTE", "待报价", "2026-05-20")
    seed_order(app, "CF-TODO-PAID", "已付款", "2026-05-20")
    seed_order(app, "CF-TODO-PROCESS", "加工中", "2026-05-20", "2026-05-12 08:00:00")
    seed_order(app, "CF-TODO-SHIP", "待发货", "2026-05-20")
    login(client)

    page = client.get("/").data.decode("utf-8")

    assert "待办提醒" in page
    for title in ["今天到期", "待报价", "已付款未下板", "加工中超时", "待发货"]:
        assert title in page
    for order_no in ["CF-TODO-DUE", "CF-TODO-QUOTE", "CF-TODO-PAID", "CF-TODO-PROCESS", "CF-TODO-SHIP"]:
        assert order_no in page
    assert "todo-reminder-grid" in page


def test_sales_dashboard_only_shows_sales_related_todos(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "sales01", "sales123", "sales")
    seed_order(app, "CF-TODO-QUOTE", "待报价")
    seed_order(app, "CF-TODO-PAID", "已付款")
    seed_order(app, "CF-TODO-PROCESS", "加工中", "2026-05-20", "2026-05-12 08:00:00")
    seed_order(app, "CF-TODO-SHIP", "待发货")

    login(client, "sales01", "sales123")
    page = client.get("/").data.decode("utf-8")

    assert "待报价" in page
    assert "已付款未下板" in page
    assert "待发货" in page
    assert 'data-todo-key="processing_timeout"' not in page


def test_production_dashboard_only_shows_production_related_todos(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "worker", "worker123", "production")
    seed_order(app, "CF-TODO-QUOTE", "待报价")
    seed_order(app, "CF-TODO-PAID", "已付款")
    seed_order(app, "CF-TODO-PROCESS", "加工中", "2026-05-20", "2026-05-12 08:00:00")
    seed_order(app, "CF-TODO-DUE", "待质检", "2026-05-14")

    login(client, "worker", "worker123")
    page = client.get("/").data.decode("utf-8")

    assert "已付款未下板" in page
    assert "加工中超时" in page
    assert "今天到期" in page
    assert 'data-todo-key="pending_quote"' not in page


def test_finance_dashboard_shows_due_and_shipping_todos_only(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "finance01", "finance123", "finance")
    seed_order(app, "CF-TODO-DUE", "已报价", "2026-05-14")
    seed_order(app, "CF-TODO-SHIP", "待发货")
    seed_order(app, "CF-TODO-QUOTE", "待报价")

    logout(client)
    login(client, "finance01", "finance123")
    page = client.get("/").data.decode("utf-8")

    assert "今天到期" in page
    assert "待发货" in page
    assert 'data-todo-key="pending_quote"' not in page


def test_todo_reminder_css_has_mobile_layout():
    css = open("static/css/style.css", encoding="utf-8").read()

    assert ".todo-reminder-grid" in css
    assert ".todo-card" in css
    assert ".todo-reminder-grid" in css and "grid-template-columns: 1fr;" in css
