-- One row per order, with its line-item totals.
with lines as (
    select
        order_id,
        count(*)        as line_count,
        sum(quantity)   as total_quantity,
        sum(net_amount) as net_revenue
    from {{ ref('stg_lineitems') }}
    group by order_id
)
select
    o.order_id,
    o.customer_id,
    o.order_date,
    o.order_status,
    o.order_priority,
    l.line_count,
    l.total_quantity,
    l.net_revenue
from {{ ref('stg_orders') }} o
join lines l on o.order_id = l.order_id
