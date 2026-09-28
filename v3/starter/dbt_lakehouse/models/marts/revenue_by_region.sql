-- Net revenue per region and order year: a small table to chart or query from Trino/DuckDB.
select
    c.region_name,
    year(o.order_date)          as order_year,
    count(*)                    as orders,
    round(sum(o.net_revenue), 2) as net_revenue
from {{ ref('fct_orders') }} o
join {{ ref('dim_customers') }} c on o.customer_id = c.customer_id
group by 1, 2
