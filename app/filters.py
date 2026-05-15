from datetime import datetime


def register_filters(app):
    @app.template_filter("money")
    def money(value):
        try:
            return f"{float(value or 0):,.2f}"
        except (TypeError, ValueError):
            return "0.00"

    @app.template_filter("percent")
    def percent(value):
        try:
            return f"{float(value or 0):.2f}%"
        except (TypeError, ValueError):
            return "0.00%"

    @app.template_filter("date_text")
    def date_text(value):
        if not value:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        return str(value)[:16]
