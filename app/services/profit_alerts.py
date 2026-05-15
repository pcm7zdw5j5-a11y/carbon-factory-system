def profit_alert_for_values(profit, margin_rate):
    profit_value = float(profit or 0)
    margin_value = float(margin_rate or 0)
    if profit_value < 0:
        return {"code": "loss", "label": "亏损订单"}
    if margin_value < 10:
        return {"code": "danger", "label": "危险利润"}
    if margin_value < 20:
        return {"code": "low", "label": "低利润"}
    return {"code": "normal", "label": ""}


def order_profit_alert(order):
    if not order:
        return {"code": "normal", "label": ""}
    return profit_alert_for_values(order["profit"], order["margin_rate"])
