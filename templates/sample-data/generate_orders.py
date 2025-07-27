        cat > /tmp/generate_sample_data.py << 'PYTHON_SCRIPT'
import csv
import random
from datetime import datetime, timedelta

# Generate enhanced orders data for DuckDB 1.3.0 testing
orders = []
base_date = datetime(2023, 1, 1)

product_categories = ['Electronics', 'Clothing', 'Books', 'Home', 'Sports', 'Beauty', 'Automotive']
regions = ['North', 'South', 'East', 'West', 'Central']
channels = ['Online', 'Store', 'Mobile App', 'Phone']

for i in range(10000):  # Increased sample size
    order_date = base_date + timedelta(days=random.randint(0, 500))
    quantity = random.randint(1, 10)
    unit_price = round(random.uniform(5, 1000), 2)
    discount = round(random.uniform(0, 0.4), 2)
    shipping_cost = round(random.uniform(0, 50), 2)
    
    orders.append({
        'order_id': f'ORD-{i+1:07d}',
        'customer_id': f'CUST-{random.randint(1, 2000):06d}',
        'order_date': order_date.strftime('%Y-%m-%d'),
        'product_category': random.choice(product_categories),
        'product_name': f'Product-{random.randint(1, 500)}',
        'quantity': quantity,
        'unit_price': unit_price,
        'discount': discount,
        'shipping_cost': shipping_cost,
        'total_amount': round(quantity * unit_price * (1 - discount) + shipping_cost, 2),
        'region': random.choice(regions),
        'sales_channel': random.choice(channels),
        'customer_segment': random.choice(['Premium', 'Standard', 'Basic']),
        'payment_method': random.choice(['Credit Card', 'Debit Card', 'PayPal', 'Cash'])
    })

# Write to CSV
with open('/tmp/sample_orders.csv', 'w', newline='') as csvfile:
    fieldnames = orders[0].keys()
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(orders)

