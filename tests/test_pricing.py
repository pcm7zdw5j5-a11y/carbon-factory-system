from app.services.pricing import calculate_cost, calculate_quote, normalize_money


def test_quote_uses_minimum_order_price_when_total_is_low():
    result = calculate_quote(
        sale_unit_price=45,
        board_count=1,
        cutting_length=0,
        cutting_unit_price=12,
        hole_count=0,
        hole_unit_price=2,
        chamfer_count=0,
        chamfer_unit_price=3,
        polishing_fee=0,
        packaging_fee=50,
        shipping_fee=0,
        other_fee=0,
        is_urgent=False,
        urgent_rate=0.2,
        include_tax=False,
        tax_rate=0.13,
    )

    assert result["material_quote"] == 45
    assert result["quote_subtotal"] == 95
    assert result["quote_total"] == 300


def test_quote_calculates_processing_urgent_and_tax_fees():
    result = calculate_quote(
        sale_unit_price=227,
        board_count=2,
        cutting_length=8,
        cutting_unit_price=12,
        hole_count=10,
        hole_unit_price=2,
        chamfer_count=4,
        chamfer_unit_price=3,
        polishing_fee=30,
        packaging_fee=50,
        shipping_fee=18,
        other_fee=10,
        is_urgent=True,
        urgent_rate=0.2,
        include_tax=True,
        tax_rate=0.13,
    )

    assert result["material_quote"] == 454
    assert result["cutting_fee"] == 96
    assert result["hole_fee"] == 20
    assert result["chamfer_fee"] == 12
    assert result["quote_subtotal"] == 690
    assert result["urgent_fee"] == 138
    assert result["tax_fee"] == 89.7
    assert result["quote_total"] == 917.7


def test_cost_profit_and_margin_use_adjusted_final_quote():
    result = calculate_cost(
        cost_unit_price=147.55,
        board_count=2,
        labor_cost=80,
        machine_cost=60,
        packaging_cost=20,
        shipping_cost=15,
        platform_fee=30,
        other_cost=10,
        final_quote=880,
    )

    assert result["material_cost"] == 295.1
    assert result["total_cost"] == 510.1
    assert result["profit"] == 369.9
    assert result["margin_rate"] == normalize_money(369.9 / 880 * 100)
