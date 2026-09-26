select
    orderkey      as order_id,
    linenumber    as line_number,
    quantity,
    extendedprice as extended_price,
    discount,
    extendedprice * (1 - discount) as net_amount,
    returnflag    as return_flag,
    shipdate      as ship_date
from {{ source('samples', 'lineitem') }}
