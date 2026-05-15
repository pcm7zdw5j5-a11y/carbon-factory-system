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


def create_search_order(client):
    response = client.post(
        "/orders/new",
        data={
            "order_no": "CF-SEARCH-555",
            "source": "淘宝",
            "customer_name": "全局搜索客户",
            "customer_contact": "13955556666",
            "product_name": "搜索测试产品",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "1",
            "board_count": "1",
            "status": "已报价",
            "final_quote": "500",
            "notes": "全局备注关键字",
            "drawing_file": (io.BytesIO(b"fake pdf"), "global_drawing.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 302
    with client.application.app_context():
        order = get_db().execute(
            "SELECT * FROM orders WHERE order_no = ?",
            ("CF-SEARCH-555",),
        ).fetchone()
        get_db().execute(
            """
            UPDATE orders
            SET tracking_number = ?, shipping_company = ?, shipped_at = ?
            WHERE id = ?
            """,
            ("SF555888", "顺丰", "2026-05-14 10:00", order["id"]),
        )
        get_db().commit()
        return order


def test_global_search_box_is_rendered_on_desktop_and_mobile(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    page = client.get("/").data.decode("utf-8")

    assert "global-search-form" in page
    assert "mobile-global-search" in page
    assert 'action="/search"' in page
    assert "订单编号、客户、手机号、产品、图纸、快递、备注" in page


def test_global_search_returns_grouped_order_customer_and_file_results(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    order = create_search_order(client)

    page = client.get("/search?q=555").data.decode("utf-8")

    assert "搜索结果" in page
    assert "订单" in page
    assert "客户" in page
    assert "文件" in page
    assert "CF-SEARCH-555" in page
    assert "全局搜索客户" in page
    assert "13955556666" in page
    assert "SF555888" in page
    assert "global_drawing.pdf" in page
    assert f"/orders/{order['id']}" in page


def test_global_search_supports_product_notes_file_and_tracking_number(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    create_search_order(client)

    assert "搜索测试产品" in client.get("/search?q=搜索测试").data.decode("utf-8")
    assert "全局备注关键字" in client.get("/search?q=备注关键字").data.decode("utf-8")
    assert "global_drawing.pdf" in client.get("/search?q=drawing").data.decode("utf-8")
    assert "SF555888" in client.get("/search?q=SF555").data.decode("utf-8")
