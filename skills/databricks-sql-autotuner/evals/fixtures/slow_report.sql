-- Slow report: monthly revenue by product category and region
-- Typical complaint: times out after ~8 minutes on the prod cluster

SELECT
    p.category,
    r.region_name,
    DATE_TRUNC('month', o.order_date) AS order_month,
    COUNT(DISTINCT o.order_id)        AS order_count,
    SUM(ol.quantity * ol.unit_price)  AS gross_revenue,
    SUM(ol.quantity * ol.unit_price)
        - SUM(ol.discount_amount)     AS net_revenue
FROM orders o
JOIN order_lines ol
    ON o.order_id = ol.order_id
JOIN products p
    ON ol.product_id = p.product_id
JOIN regions r
    ON o.region_code = r.region_code
WHERE o.order_date BETWEEN '2023-01-01' AND '2023-12-31'
  AND o.status != 'CANCELLED'
GROUP BY
    p.category,
    r.region_name,
    DATE_TRUNC('month', o.order_date)
ORDER BY
    order_month,
    gross_revenue DESC
