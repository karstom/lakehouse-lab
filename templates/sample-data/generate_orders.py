#!/usr/bin/env python3
"""
Sample Orders Data Generator
Generates realistic sample order data for Lakehouse Lab testing
"""

import csv
import random
from datetime import datetime, timedelta

def generate_sample_orders():
    """Generate sample orders data"""
    print("🔧 Generating sample orders data...")
    
    # Generate enhanced orders data for DuckDB 1.3.0 testing
    orders = []
    base_date = datetime(2023, 1, 1)
    
    product_categories = ['Electronics', 'Clothing', 'Books', 'Home', 'Sports', 'Beauty', 'Automotive']
    product_names = {
        'Electronics': ['Laptop', 'Smartphone', 'Tablet', 'Headphones', 'Camera'],
        'Clothing': ['T-Shirt', 'Jeans', 'Dress', 'Jacket', 'Shoes'],
        'Books': ['Novel', 'Textbook', 'Cookbook', 'Biography', 'Manual'],
        'Home': ['Chair', 'Table', 'Lamp', 'Pillow', 'Curtains'],
        'Sports': ['Basketball', 'Soccer Ball', 'Tennis Racket', 'Gym Equipment', 'Running Shoes'],
        'Beauty': ['Shampoo', 'Lipstick', 'Perfume', 'Face Cream', 'Nail Polish'],
        'Automotive': ['Oil Filter', 'Brake Pads', 'Car Charger', 'Floor Mats', 'Air Freshener']
    }
    
    cities = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 'Philadelphia', 'San Antonio']
    states = ['NY', 'CA', 'IL', 'TX', 'AZ', 'PA', 'TX']
    
    # Generate 1000 orders
    for i in range(1000):
        category = random.choice(product_categories)
        product = random.choice(product_names[category])
        
        order_date = base_date + timedelta(days=random.randint(0, 365))
        quantity = random.randint(1, 5)
        unit_price = round(random.uniform(10.0, 500.0), 2)
        total_amount = round(quantity * unit_price, 2)
        
        city_idx = random.randint(0, len(cities)-1)
        city = cities[city_idx]
        state = states[city_idx]
        
        order = {
            'order_id': f'ORD-{1000 + i}',
            'customer_id': f'CUST-{random.randint(1, 200)}',
            'product_name': product,
            'product_category': category,
            'quantity': quantity,
            'unit_price': unit_price,
            'total_amount': total_amount,
            'order_date': order_date.strftime('%Y-%m-%d'),
            'ship_city': city,
            'ship_state': state,
            'order_status': random.choice(['Pending', 'Shipped', 'Delivered', 'Cancelled'])
        }
        orders.append(order)
    
    # Write to CSV
    output_file = '/tmp/sample_orders.csv'
    fieldnames = ['order_id', 'customer_id', 'product_name', 'product_category', 
                  'quantity', 'unit_price', 'total_amount', 'order_date', 
                  'ship_city', 'ship_state', 'order_status']
    
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(orders)
    
    print(f"✅ Generated {len(orders)} sample orders")
    print(f"📝 Data saved to: {output_file}")
    
    # Show sample statistics
    categories_count = {}
    for order in orders:
        cat = order['product_category']
        categories_count[cat] = categories_count.get(cat, 0) + 1
    
    print("📊 Sample data statistics:")
    for category, count in sorted(categories_count.items()):
        print(f"   {category}: {count} orders")
    
    total_revenue = sum(float(order['total_amount']) for order in orders)
    print(f"💰 Total sample revenue: ${total_revenue:,.2f}")
    
    return output_file

if __name__ == "__main__":
    generate_sample_orders()