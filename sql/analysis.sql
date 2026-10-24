-- SQLite dialect. Run scripts/run_sql.py to create retail from bundled Parquet.
-- USD amounts stored in integer cents at the fixed 2011-12-09 rate: 1 GBP = 1.5688 USD.
-- Source GBP remains intact; each line converts before aggregation. Return rows have is_return = 1.

-- 1. Reconcile gross sales, returns, and net sales.
SELECT ROUND(SUM(sales_cents_usd)/100.0, 2) AS gross_sales_usd,
       ROUND(SUM(return_cents_usd)/100.0, 2) AS cancellation_value_usd,
       ROUND(SUM(net_cents_usd)/100.0, 2) AS net_sales_usd,
       COUNT(DISTINCT CASE WHEN is_return = 0 THEN InvoiceNo END) AS purchase_orders
FROM retail;

-- 2. Monthly net sales: boundary months can be incomplete.
SELECT month, SUM(net_cents_usd)/100.0 AS net_sales_usd
FROM retail GROUP BY month ORDER BY month;

-- 3. Country concentration.
WITH country_sales AS (
    SELECT Country, SUM(net_cents_usd) AS net_cents_usd FROM retail GROUP BY Country
)
SELECT Country, net_cents_usd/100.0 AS net_sales_usd,
       ROUND(100.0 * net_cents_usd / NULLIF((SELECT SUM(net_cents_usd) FROM country_sales),0),2) AS net_sales_share_pct
FROM country_sales ORDER BY net_cents_usd DESC LIMIT 10;

-- 4. Top products including cancellation impact.
SELECT StockCode, Description, SUM(sales_cents_usd)/100.0 AS gross_sales_usd,
       SUM(return_cents_usd)/100.0 AS returns_usd, SUM(net_cents_usd)/100.0 AS net_sales_usd
FROM retail GROUP BY StockCode, Description ORDER BY net_sales_usd DESC LIMIT 10;

-- 5. Invoice purchase value before returns; anonymous invoices included.
WITH purchases AS (
    SELECT InvoiceNo, SUM(sales_cents_usd)/100.0 AS order_value
    FROM retail WHERE is_return = 0 GROUP BY InvoiceNo
)
SELECT ROUND(AVG(order_value),2) AS average_purchase_order_value_usd FROM purchases;

-- 6. Sales lacking known customer identifiers.
SELECT COUNT(*) AS anonymous_lines, SUM(net_cents_usd)/100.0 AS anonymous_net_sales_usd
FROM retail WHERE CustomerID IS NULL;
