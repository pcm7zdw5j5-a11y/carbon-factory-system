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


def test_price_items_have_inventory_columns_after_migration(tmp_path):
    app = make_app(tmp_path)

    with app.app_context():
        columns = {
            row["name"]
            for row in get_db().execute("PRAGMA table_info(price_items)").fetchall()
        }

    assert "current_stock" in columns
    assert "safety_stock" in columns


def test_dashboard_shows_purchase_reminder_when_stock_is_low(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    with app.app_context():
        db = get_db()
        db.execute(
            """
            UPDATE price_items
            SET current_stock = 2, safety_stock = 5
            WHERE specification = ? AND thickness = ?
            """,
            ("400×500", "3mm"),
        )
        db.commit()

    page = client.get("/").data.decode("utf-8")

    assert "采购提醒" in page
    assert "400×500" in page
    assert "3mm" in page
    assert "建议采购数量" in page
    assert "3" in page
    assert "/purchase-list" in page


def test_purchase_list_page_renders_low_stock_items_and_print_button(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    with app.app_context():
        db = get_db()
        db.execute(
            """
            UPDATE price_items
            SET current_stock = 1, safety_stock = 4
            WHERE specification = ? AND thickness = ?
            """,
            ("400×500", "2mm"),
        )
        db.commit()

    page = client.get("/purchase-list").data.decode("utf-8")

    assert "采购清单" in page
    assert "打印采购清单" in page
    assert "400×500" in page
    assert "2mm" in page
    assert "建议采购数量" in page
    assert "window.print()" in page
