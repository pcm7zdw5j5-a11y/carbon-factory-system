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


def create_order(client, order_no, status):
    login(client)
    response = client.post(
        "/orders/new",
        data={
            "order_no": order_no,
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
            "status": status,
            "final_quote": "880",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302


def get_order(app, order_no):
    with app.app_context():
        return get_db().execute("SELECT * FROM orders WHERE order_no = ?", (order_no,)).fetchone()


def test_status_history_table_exists(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        columns = get_db().execute("PRAGMA table_info(status_history)").fetchall()

    assert [column["name"] for column in columns] == [
        "id",
        "order_id",
        "old_status",
        "new_status",
        "changed_at",
    ]


def test_next_status_from_quoted_to_paid(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_order(client, "CF-STATUS-001", "已报价")
    order = get_order(app, "CF-STATUS-001")

    response = client.post(f"/orders/{order['id']}/status/next", follow_redirects=True)

    assert response.status_code == 200
    assert get_order(app, "CF-STATUS-001")["status"] == "已付款"
    assert "订单状态已更新为：已付款".encode("utf-8") in response.data


def test_next_status_records_history(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_order(client, "CF-HISTORY-001", "已报价")
    order = get_order(app, "CF-HISTORY-001")

    client.post(f"/orders/{order['id']}/status/next")

    with app.app_context():
        rows = get_db().execute(
            "SELECT * FROM status_history WHERE order_id = ?",
            (order["id"],),
        ).fetchall()

    assert len(rows) == 1
    assert rows[0]["old_status"] == "已报价"
    assert rows[0]["new_status"] == "已付款"
    assert rows[0]["changed_at"]


def test_cancel_order_records_history_and_detail_shows_descending_history(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_order(client, "CF-HISTORY-002", "已报价")
    order = get_order(app, "CF-HISTORY-002")

    client.post(f"/orders/{order['id']}/status/next")
    response = client.post(f"/orders/{order['id']}/cancel", follow_redirects=True)
    page = response.data.decode("utf-8")

    with app.app_context():
        rows = get_db().execute(
            "SELECT old_status, new_status FROM status_history WHERE order_id = ? ORDER BY changed_at DESC, id DESC",
            (order["id"],),
        ).fetchall()

    assert [tuple(row) for row in rows] == [("已付款", "已取消"), ("已报价", "已付款")]
    assert "状态变更历史" in page
    assert page.index("已付款 → 已取消") < page.index("已报价 → 已付款")


def test_order_list_shows_next_button_and_returns_to_list(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_order(client, "CF-STATUS-LIST", "已报价")
    order = get_order(app, "CF-STATUS-LIST")

    order_list = client.get("/orders")
    assert "下一步：已付款".encode("utf-8") in order_list.data

    response = client.post(
        f"/orders/{order['id']}/status/next",
        data={"return_to": "list"},
        follow_redirects=True,
    )

    assert response.request.path == "/orders"
    assert get_order(app, "CF-STATUS-LIST")["status"] == "已付款"


def test_next_status_from_paid_to_pending_board(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_order(client, "CF-STATUS-002", "已付款")
    order = get_order(app, "CF-STATUS-002")

    client.post(f"/orders/{order['id']}/status/next")

    assert get_order(app, "CF-STATUS-002")["status"] == "待下板"


def test_next_status_from_pending_board_to_processing(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_order(client, "CF-STATUS-003", "待下板")
    order = get_order(app, "CF-STATUS-003")

    client.post(f"/orders/{order['id']}/status/next")

    assert get_order(app, "CF-STATUS-003")["status"] == "加工中"


def test_completed_and_cancelled_orders_do_not_show_next_button(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_order(client, "CF-STATUS-004", "已完成")
    create_order(client, "CF-STATUS-005", "已取消")
    completed = get_order(app, "CF-STATUS-004")
    cancelled = get_order(app, "CF-STATUS-005")

    completed_detail = client.get(f"/orders/{completed['id']}")
    cancelled_detail = client.get(f"/orders/{cancelled['id']}")
    order_list = client.get("/orders")

    assert "下一步：".encode("utf-8") not in completed_detail.data
    assert "下一步：".encode("utf-8") not in cancelled_detail.data
    assert b"/orders/%d/status/next" % completed["id"] not in order_list.data
    assert b"/orders/%d/status/next" % cancelled["id"] not in order_list.data


def test_cancel_order_updates_status_to_cancelled(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_order(client, "CF-STATUS-006", "已报价")
    order = get_order(app, "CF-STATUS-006")

    response = client.post(f"/orders/{order['id']}/cancel", follow_redirects=True)

    assert response.status_code == 200
    assert get_order(app, "CF-STATUS-006")["status"] == "已取消"
    assert "订单状态已更新为：已取消".encode("utf-8") in response.data


def test_sales_can_only_advance_sales_statuses(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "sales01", "sales123", "sales")
    create_order(client, "CF-ROLE-SALES-1", "已报价")
    create_order(client, "CF-ROLE-SALES-2", "已付款")
    sales_order = get_order(app, "CF-ROLE-SALES-1")
    paid_order = get_order(app, "CF-ROLE-SALES-2")
    logout(client)
    login(client, "sales01", "sales123")

    client.post(f"/orders/{sales_order['id']}/status/next")
    denied = client.post(f"/orders/{paid_order['id']}/status/next", follow_redirects=True)

    assert get_order(app, "CF-ROLE-SALES-1")["status"] == "已付款"
    assert get_order(app, "CF-ROLE-SALES-2")["status"] == "已付款"
    assert "无权限推进当前状态".encode("utf-8") in denied.data


def test_production_can_advance_production_statuses_and_finance_cannot(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "worker", "worker123", "production")
    create_user(app, "finance01", "finance123", "finance")
    create_order(client, "CF-ROLE-PROD-1", "已付款")
    create_order(client, "CF-ROLE-PROD-2", "待下板")
    paid_order = get_order(app, "CF-ROLE-PROD-1")
    board_order = get_order(app, "CF-ROLE-PROD-2")

    logout(client)
    login(client, "worker", "worker123")
    client.post(f"/orders/{paid_order['id']}/status/next")
    client.post(f"/orders/{board_order['id']}/status/next")

    assert get_order(app, "CF-ROLE-PROD-1")["status"] == "待下板"
    assert get_order(app, "CF-ROLE-PROD-2")["status"] == "加工中"

    logout(client)
    login(client, "finance01", "finance123")
    denied = client.post(f"/orders/{paid_order['id']}/status/next", follow_redirects=True)

    assert get_order(app, "CF-ROLE-PROD-1")["status"] == "待下板"
    assert "无权限推进当前状态".encode("utf-8") in denied.data
