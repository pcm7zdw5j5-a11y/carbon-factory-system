from app import create_app
from tests.helpers import create_user, login, logout


def make_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "carbon_factory.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )


def test_board_calculator_service_computes_layout():
    from app.services.board_calculator import calculate_rect_board_usage

    result = calculate_rect_board_usage(
        board_width=400,
        board_height=500,
        part_width=100,
        part_height=100,
        quantity=25,
        margin=10,
        spacing=5,
    )

    assert result["pieces_per_row"] == 3
    assert result["rows_per_board"] == 4
    assert result["pieces_per_board"] == 12
    assert result["needed_boards"] == 3
    assert result["utilization_rate"] == 41.67


def test_board_calculator_rejects_invalid_dimensions():
    from app.services.board_calculator import calculate_rect_board_usage

    result = calculate_rect_board_usage(
        board_width=100,
        board_height=100,
        part_width=200,
        part_height=80,
        quantity=1,
        margin=10,
        spacing=5,
    )

    assert result["error"]
    assert result["pieces_per_board"] == 0


def test_board_calculator_page_and_order_form_are_available(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    page = client.get("/board-calculator").data.decode("utf-8")
    form_page = client.get("/orders/new").data.decode("utf-8")

    assert "标准矩形件用板计算" in page
    assert "data-board-calculator" in page
    assert "每张板排多少件" in page
    assert "写入预计使用板数" in form_page
    assert "data-write-board-count" in form_page
    assert "board_calculator.js" in form_page


def test_board_calculator_menu_hidden_from_finance(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "finance01", "finance123", "finance")
    login(client)
    admin_page = client.get("/").data.decode("utf-8")
    assert "用板计算" in admin_page

    logout(client)
    login(client, "finance01", "finance123")
    finance_page = client.get("/").data.decode("utf-8")
    assert "用板计算" not in finance_page
