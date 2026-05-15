from werkzeug.security import check_password_hash

from app import create_app
from app.database import init_db
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


def test_users_table_and_default_admin_are_created_with_hashed_password(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        columns = get_db().execute("PRAGMA table_info(users)").fetchall()
        admin = get_db().execute("SELECT * FROM users WHERE username = 'admin'").fetchone()

    assert [column["name"] for column in columns] == [
        "id",
        "username",
        "password_hash",
        "role",
        "is_active",
        "created_at",
    ]
    assert admin["role"] == "admin"
    assert admin["is_active"] == 1
    assert admin["password_hash"] != "admin123"
    assert check_password_hash(admin["password_hash"], "admin123")


def test_admin_is_created_when_users_table_exists_without_admin(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM users WHERE username = 'admin'")
        db.execute(
            """
            INSERT INTO users (username, password_hash, role, is_active, created_at)
            VALUES ('sales_only', 'placeholder', 'sales', 1, datetime('now', 'localtime'))
            """
        )
        db.commit()

        before_orders = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        before_prices = db.execute("SELECT COUNT(*) FROM price_items").fetchone()[0]
        init_db()
        admin = db.execute("SELECT * FROM users WHERE username = 'admin'").fetchone()
        after_orders = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        after_prices = db.execute("SELECT COUNT(*) FROM price_items").fetchone()[0]

    assert admin is not None
    assert check_password_hash(admin["password_hash"], "admin123")
    assert after_orders == before_orders
    assert after_prices == before_prices


def test_unauthenticated_user_is_redirected_to_login(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_logout_and_default_password_warning(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()

    login_response = login(client)
    assert login_response.status_code == 200
    assert "当前登录：admin".encode("utf-8") in login_response.data
    assert "默认密码".encode("utf-8") in login_response.data

    logout_response = logout(client, follow_redirects=False)
    assert logout_response.status_code == 302

    protected_response = client.get("/", follow_redirects=False)
    assert protected_response.status_code == 302
    assert "/login" in protected_response.headers["Location"]


def test_login_fails_for_bad_password_and_inactive_user(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "disabled", "disabled123", "sales", is_active=0)

    bad_password = login(client, "admin", "wrong")
    assert "用户名或密码错误".encode("utf-8") in bad_password.data

    disabled_user = login(client, "disabled", "disabled123")
    assert "账号已停用".encode("utf-8") in disabled_user.data


def test_admin_can_create_user_and_sales_cannot_access_user_management(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    response = client.post(
        "/users",
        data={"username": "sales01", "password": "sales123", "role": "sales"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        user = get_db().execute("SELECT * FROM users WHERE username = 'sales01'").fetchone()
    assert user["role"] == "sales"
    assert check_password_hash(user["password_hash"], "sales123")

    logout(client)
    login(client, "sales01", "sales123")
    forbidden = client.get("/users")
    assert forbidden.status_code == 403
    assert "无权限访问".encode("utf-8") in forbidden.data


def test_menus_are_hidden_by_role(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "worker", "worker123", "production")
    login(client, "worker", "worker123")

    response = client.get("/")

    assert "用户管理".encode("utf-8") not in response.data
    assert "新建订单".encode("utf-8") not in response.data
    assert "月度统计".encode("utf-8") not in response.data
    assert "订单列表".encode("utf-8") in response.data


def create_order(client, order_no="CF-AUTH-ORDER"):
    response = client.post(
        "/orders/new",
        data={
            "order_no": order_no,
            "source": "淘宝",
            "customer_name": "权限测试客户",
            "customer_contact": "13800000000",
            "product_name": "权限测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "10",
            "board_count": "2",
            "status": "已报价",
            "final_quote": "880",
            "labor_cost": "80",
            "machine_cost": "60",
            "packaging_cost": "20",
            "shipping_cost": "15",
            "platform_fee": "30",
            "other_cost": "10",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    with client.application.app_context():
        return get_db().execute("SELECT * FROM orders WHERE order_no = ?", (order_no,)).fetchone()


def test_sensitive_money_sections_are_hidden_by_role(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "sales01", "sales123", "sales")
    create_user(app, "worker", "worker123", "production")
    login(client)
    order = create_order(client)

    logout(client)
    login(client, "worker", "worker123")
    production_detail = client.get(f"/orders/{order['id']}").data.decode("utf-8")
    assert "报价明细" not in production_detail
    assert "成本明细" not in production_detail
    assert "利润核算" not in production_detail
    assert "¥880.00" not in production_detail

    logout(client)
    login(client, "sales01", "sales123")
    sales_detail = client.get(f"/orders/{order['id']}").data.decode("utf-8")
    assert "报价明细" in sales_detail
    assert "成本明细" not in sales_detail
    assert "利润核算" not in sales_detail


def test_finance_can_edit_cost_but_cannot_delete_order(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "finance01", "finance123", "finance")
    login(client)
    order = create_order(client, "CF-FINANCE-ORDER")

    logout(client)
    login(client, "finance01", "finance123")
    response = client.post(
        f"/orders/{order['id']}/costs/edit",
        data={
            "cost_unit_price": "200",
            "labor_cost": "100",
            "machine_cost": "80",
            "packaging_cost": "20",
            "shipping_cost": "15",
            "platform_fee": "30",
            "other_cost": "10",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "成本信息已更新".encode("utf-8") in response.data
    with app.app_context():
        updated = get_db().execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()
    assert updated["material_cost"] == 400
    assert updated["total_cost"] == 655
    assert updated["profit"] == 225

    forbidden = client.post(f"/orders/{order['id']}/delete")
    assert forbidden.status_code == 403
    assert "无权限访问".encode("utf-8") in forbidden.data
