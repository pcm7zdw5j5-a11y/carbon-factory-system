import io

from app import create_app
from app.database import get_db
from tests.helpers import login


def make_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "carbon_factory.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )


def test_default_prices_are_seeded(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        row = get_db().execute(
            "SELECT sale_price, cost_price FROM price_items WHERE specification = ? AND thickness = ?",
            ("400×500", "3mm"),
        ).fetchone()

    assert row["sale_price"] == 227
    assert row["cost_price"] == 147.55


def test_create_order_persists_quote_cost_and_uploaded_drawing(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    response = client.post(
        "/orders/new",
        data={
            "order_no": "CF-TEST-001",
            "source": "淘宝",
            "customer_name": "测试客户",
            "customer_contact": "13800000000",
            "product_name": "碳纤维测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "10",
            "board_count": "2",
            "delivery_date": "2026-05-20",
            "processing_requirements": "切割打孔",
            "notes": "测试订单",
            "status": "已报价",
            "cutting_length": "8",
            "cutting_unit_price": "12",
            "hole_count": "10",
            "hole_unit_price": "2",
            "chamfer_count": "4",
            "chamfer_unit_price": "3",
            "polishing_fee": "30",
            "packaging_fee": "50",
            "shipping_fee": "18",
            "other_fee": "10",
            "is_urgent": "1",
            "urgent_rate": "0.2",
            "include_tax": "1",
            "tax_rate": "0.13",
            "final_quote": "880",
            "labor_cost": "80",
            "machine_cost": "60",
            "packaging_cost": "20",
            "shipping_cost": "15",
            "platform_fee": "30",
            "other_cost": "10",
            "drawing_file": (io.BytesIO(b"fake pdf"), "drawing.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    assert response.status_code == 302

    with app.app_context():
        order = get_db().execute("SELECT * FROM orders WHERE order_no = ?", ("CF-TEST-001",)).fetchone()

    assert order["final_quote"] == 880
    assert order["profit"] == 369.9
    assert order["drawing_original_name"] == "drawing.pdf"


def test_monthly_statistics_page_loads(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    response = client.get("/statistics")

    assert response.status_code == 200
    assert "月度统计".encode("utf-8") in response.data
