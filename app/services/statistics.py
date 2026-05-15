from datetime import datetime


def month_key(year, month):
    return f"{int(year):04d}-{int(month):02d}"


def build_monthly_statistics(db, year, month_number, order_sources, report_statuses):
    key = month_key(year, month_number)
    summary = db.execute(
        """
        SELECT
            COUNT(*) AS total_orders,
            SUM(CASE WHEN status = '已完成' THEN 1 ELSE 0 END) AS completed_orders,
            COALESCE(SUM(final_quote), 0) AS sales_total,
            COALESCE(SUM(material_cost), 0) AS material_cost_total,
            COALESCE(SUM(labor_cost), 0) AS labor_cost_total,
            COALESCE(SUM(machine_cost), 0) AS machine_cost_total,
            COALESCE(SUM(packaging_cost), 0) AS packaging_cost_total,
            COALESCE(SUM(shipping_cost), 0) AS shipping_cost_total,
            COALESCE(SUM(shipping_freight), 0) AS shipping_freight_total,
            COALESCE(SUM(platform_fee), 0) AS platform_fee_total,
            COALESCE(SUM(other_cost), 0) AS other_cost_total,
            COALESCE(SUM(total_cost), 0) AS cost_total,
            COALESCE(SUM(profit), 0) AS profit_total,
            COALESCE(AVG(CASE WHEN final_quote > 0 THEN margin_rate END), 0) AS avg_margin_rate,
            (
                SELECT COUNT(DISTINCT oe.order_id)
                FROM order_exceptions oe
                WHERE substr(oe.created_at, 1, 7) = ?
            ) AS exception_order_count,
            (
                SELECT COUNT(*)
                FROM order_exceptions oe
                WHERE substr(oe.created_at, 1, 7) = ?
                  AND oe.exception_type = '返工'
            ) AS rework_count
        FROM orders
        WHERE substr(created_at, 1, 7) = ?
        """,
        (key, key, key),
    ).fetchone()
    source_sales_rows = db.execute(
        """
        SELECT source, COALESCE(SUM(final_quote), 0) AS total
        FROM orders
        WHERE substr(created_at, 1, 7) = ?
        GROUP BY source
        ORDER BY total DESC
        """,
        (key,),
    ).fetchall()
    status_count_rows = db.execute(
        """
        SELECT status, COUNT(*) AS total
        FROM orders
        WHERE substr(created_at, 1, 7) = ?
        GROUP BY status
        ORDER BY total DESC
        """,
        (key,),
    ).fetchall()
    detail_orders = db.execute(
        """
        SELECT *
        FROM orders
        WHERE substr(created_at, 1, 7) = ?
        ORDER BY created_at ASC, id ASC
        """,
        (key,),
    ).fetchall()
    source_sales_map = {row["source"] or "其他": row["total"] for row in source_sales_rows}
    status_count_map = {row["status"] or "待审核": row["total"] for row in status_count_rows}
    return {
        "year": year,
        "month": month_number,
        "month_key": key,
        "print_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
        "source_sales": [
            {"source": source, "total": source_sales_map.get(source, 0)}
            for source in order_sources
        ],
        "status_counts": [
            {"status": status, "total": status_count_map.get(status, 0)}
            for status in report_statuses
        ],
        "detail_orders": detail_orders,
    }
