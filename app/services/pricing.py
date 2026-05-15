from decimal import Decimal, ROUND_HALF_UP


MINIMUM_ORDER_PRICE = Decimal("300")


def normalize_money(value):
    amount = Decimal(str(value or 0))
    return float(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _number(value):
    return Decimal(str(value or 0))


def calculate_quote(
    *,
    sale_unit_price,
    board_count,
    cutting_length,
    cutting_unit_price,
    hole_count,
    hole_unit_price,
    chamfer_count,
    chamfer_unit_price,
    polishing_fee,
    packaging_fee,
    shipping_fee,
    other_fee,
    is_urgent,
    urgent_rate,
    include_tax,
    tax_rate,
):
    material_quote = _number(sale_unit_price) * _number(board_count)
    cutting_fee = _number(cutting_length) * _number(cutting_unit_price)
    hole_fee = _number(hole_count) * _number(hole_unit_price)
    chamfer_fee = _number(chamfer_count) * _number(chamfer_unit_price)
    subtotal = (
        material_quote
        + cutting_fee
        + hole_fee
        + chamfer_fee
        + _number(polishing_fee)
        + _number(packaging_fee)
        + _number(shipping_fee)
        + _number(other_fee)
    )
    urgent_fee = subtotal * _number(urgent_rate) if is_urgent else Decimal("0")
    tax_fee = subtotal * _number(tax_rate) if include_tax else Decimal("0")
    quote_total = subtotal + urgent_fee + tax_fee
    if quote_total < MINIMUM_ORDER_PRICE:
        quote_total = MINIMUM_ORDER_PRICE

    return {
        "material_quote": normalize_money(material_quote),
        "cutting_fee": normalize_money(cutting_fee),
        "hole_fee": normalize_money(hole_fee),
        "chamfer_fee": normalize_money(chamfer_fee),
        "quote_subtotal": normalize_money(subtotal),
        "urgent_fee": normalize_money(urgent_fee),
        "tax_fee": normalize_money(tax_fee),
        "quote_total": normalize_money(quote_total),
    }


def calculate_cost(
    *,
    cost_unit_price,
    board_count,
    labor_cost,
    machine_cost,
    packaging_cost,
    shipping_cost,
    platform_fee,
    other_cost,
    final_quote,
):
    material_cost = _number(cost_unit_price) * _number(board_count)
    total_cost = (
        material_cost
        + _number(labor_cost)
        + _number(machine_cost)
        + _number(packaging_cost)
        + _number(shipping_cost)
        + _number(platform_fee)
        + _number(other_cost)
    )
    profit = _number(final_quote) - total_cost
    margin_rate = Decimal("0")
    if _number(final_quote) > 0:
        margin_rate = profit / _number(final_quote) * Decimal("100")

    return {
        "material_cost": normalize_money(material_cost),
        "total_cost": normalize_money(total_cost),
        "profit": normalize_money(profit),
        "margin_rate": normalize_money(margin_rate),
    }
