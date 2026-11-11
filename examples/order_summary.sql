-- Her müşterinin sipariş sayısı ve toplam harcaması.
-- Örnek veriler bu sorguya aittir ve SQLite'ta doğrudan çalışır.
WITH customers (id, name) AS (
  VALUES (1, 'Ada'), (2, 'Deniz'), (3, 'Ece')
),
orders (customer_id, amount) AS (
  VALUES (1, 120), (1, 80), (2, 150)
)
SELECT
  c.name AS customer,
  COUNT(o.customer_id) AS order_count,
  COALESCE(SUM(o.amount), 0) AS total_amount
FROM customers AS c
LEFT JOIN orders AS o ON o.customer_id = c.id
GROUP BY c.id, c.name
ORDER BY total_amount DESC, c.name;
