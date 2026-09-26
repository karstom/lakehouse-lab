-- segment_revenue: net revenue per customer market segment and order year.
--
-- Copy this file into your project's models/marts/ folder (step 3 of the lesson), then
-- replace the three ___ blanks. ref('a_model') means "the table built by that model": dbt
-- works out the full name (lakehouse.dbt_<you>.a_model) and the build order for you.
-- (Careful: dbt reads double curly braces even inside -- comments.)
select
    c.market_segment,
    year(o.order_date)            as order_year,
    count(*)                      as orders,
    count(distinct o.customer_id) as customers,
    round(sum(o.___), 2)          as net_revenue
from {{ ref('___') }} o
join {{ ref('dim_customers') }} c on o.customer_id = ___
group by 1, 2
