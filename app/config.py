ALLOWED_EXTENSIONS = {"pdf", "dxf", "dwg", "jpg", "jpeg", "png", "zip"}

ORDER_SOURCES = ["淘宝", "微信", "线下", "其他"]

ORDER_STATUSES = [
    "待审核",
    "待报价",
    "已报价",
    "已付款",
    "待下板",
    "加工中",
    "待质检",
    "待包装",
    "待发货",
    "已发货",
    "已完成",
    "已取消",
]

STATUS_FLOW = [
    "待审核",
    "待报价",
    "已报价",
    "已付款",
    "待下板",
    "加工中",
    "待质检",
    "待包装",
    "待发货",
    "已发货",
    "已完成",
]


def next_order_status(current_status):
    if current_status not in STATUS_FLOW:
        return None
    index = STATUS_FLOW.index(current_status)
    if index >= len(STATUS_FLOW) - 1:
        return None
    return STATUS_FLOW[index + 1]

DEFAULT_PRICES = [
    ("400×500", "0.2mm", 45),
    ("400×500", "0.5mm", 79),
    ("400×500", "1mm", 104),
    ("400×500", "1.5mm", 132),
    ("400×500", "2mm", 167),
    ("400×500", "2.5mm", 192),
    ("400×500", "3mm", 227),
    ("400×500", "3.5mm", 262),
    ("400×500", "4mm", 289),
    ("400×500", "5mm", 342),
    ("400×500", "6mm", 390),
    ("400×500", "7mm", 455),
    ("400×500", "8mm", 505),
    ("400×500", "9mm", 560),
    ("400×500", "10mm", 605),
    ("400×500", "15mm", 919),
    ("400×500", "20mm", 1225),
]
