select
    custkey    as customer_id,
    name       as customer_name,
    nationkey  as nation_id,
    mktsegment as market_segment,
    acctbal    as account_balance
from {{ source('samples', 'customer') }}
