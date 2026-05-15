from app import create_app
from tests.helpers import login


def make_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "carbon_factory.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )


def create_filter_order(client):
    response = client.post(
        "/orders/new",
        data={
            "order_no": "CF-555-A",
            "source": "淘宝",
            "customer_name": "张三碳板",
            "customer_contact": "13855551234",
            "product_name": "手机测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "1",
            "board_count": "1",
            "status": "加工中",
            "final_quote": "555",
            "notes": "急件备注555",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_orders_page_has_realtime_filter_data_and_clear_only(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    create_filter_order(client)

    response = client.get("/orders")
    page = response.data.decode("utf-8")

    assert "data-order-filter-form" in page
    assert "data-filter-keyword" in page
    assert "data-filter-status" in page
    assert "data-filter-source" in page
    assert "data-filter-clear" in page
    assert "data-filter-summary" in page
    assert "没有找到符合条件的订单" in page
    assert "order_filter.js" in page
    assert 'type="submit">筛选' not in page

    assert 'data-status="加工中"' in page
    assert 'data-source="淘宝"' in page
    assert 'data-order-no="CF-555-A"' in page
    assert 'data-customer="张三碳板"' in page
    assert 'data-phone="13855551234"' in page
    assert 'data-product="手机测试板"' in page
    assert 'data-remark="急件备注555"' in page


def test_realtime_filter_script_listens_to_input_and_change_events():
    script = open("static/js/order_filter.js", encoding="utf-8").read()

    assert 'addEventListener("input"' in script
    assert 'addEventListener("change"' in script
    assert "applyFilters" in script
    assert "clearFilters" in script
