import math


def to_number(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_rect_board_usage(
    *,
    board_width,
    board_height,
    part_width,
    part_height,
    quantity,
    margin=0,
    spacing=0,
):
    board_width = to_number(board_width)
    board_height = to_number(board_height)
    part_width = to_number(part_width)
    part_height = to_number(part_height)
    quantity = int(to_number(quantity))
    margin = to_number(margin)
    spacing = max(0, to_number(spacing))

    result = {
        "pieces_per_row": 0,
        "rows_per_board": 0,
        "pieces_per_board": 0,
        "needed_boards": 0,
        "utilization_rate": 0,
        "error": "",
    }

    if min(board_width, board_height, part_width, part_height, quantity) <= 0:
        result["error"] = "请输入大于 0 的板材尺寸、零件尺寸和数量。"
        return result
    if margin < 0:
        result["error"] = "边距不能小于 0。"
        return result

    usable_width = board_width - margin * 2
    usable_height = board_height - margin * 2
    if usable_width <= 0 or usable_height <= 0:
        result["error"] = "边距过大，板材可用尺寸不足。"
        return result

    pieces_per_row = math.floor((usable_width + spacing) / (part_width + spacing))
    rows_per_board = math.floor((usable_height + spacing) / (part_height + spacing))
    pieces_per_board = max(0, pieces_per_row) * max(0, rows_per_board)
    if pieces_per_board <= 0:
        result["error"] = "当前零件尺寸无法排入板材，请检查尺寸、边距和间距。"
        return result

    needed_boards = math.ceil(quantity / pieces_per_board)
    utilization_rate = (quantity * part_width * part_height) / (needed_boards * board_width * board_height) * 100

    result.update(
        {
            "pieces_per_row": pieces_per_row,
            "rows_per_board": rows_per_board,
            "pieces_per_board": pieces_per_board,
            "needed_boards": needed_boards,
            "utilization_rate": round(utilization_rate, 2),
        }
    )
    return result
