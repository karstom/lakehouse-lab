select
    regionkey as region_id,
    name      as region_name
from {{ source('samples', 'region') }}
