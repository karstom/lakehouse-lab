-- One row per customer, with nation and region.
select
    c.customer_id,
    c.customer_name,
    c.market_segment,
    c.account_balance,
    n.nation_name,
    r.region_name
from {{ ref('stg_customers') }} c
join {{ ref('stg_nations') }} n on c.nation_id = n.nation_id
join {{ ref('stg_regions') }} r on n.region_id = r.region_id
