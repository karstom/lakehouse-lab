#!/usr/bin/env python3
"""
Simple Working Dashboard
Final solution that works in your Jupyter environment
"""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

def create_sample_data():
    """Create sample business data"""
    np.random.seed(42)  # Reproducible results
    
    # Monthly business metrics
    dates = pd.date_range('2024-01-01', periods=12, freq='M')
    business_data = pd.DataFrame({
        'month': dates,
        'revenue': np.random.randint(50000, 150000, 12),
        'customers': np.random.randint(500, 2000, 12),
        'orders': np.random.randint(1000, 5000, 12)
    })
    
    # Product performance
    product_data = pd.DataFrame({
        'product': ['Analytics Platform', 'Data Engineering', 'ML Pipeline', 'Business Intelligence'],
        'users': [1250, 980, 750, 1100],
        'satisfaction': [4.2, 4.5, 4.1, 4.3],
        'revenue_share': [25, 20, 15, 30]
    })
    
    return business_data, product_data

def display_dashboard():
    """Display the complete dashboard"""
    
    print("🎯 LAKEHOUSE DASHBOARD")
    print("=" * 50)
    
    # Get data
    business_data, product_data = create_sample_data()
    
    # Key metrics
    total_revenue = business_data['revenue'].sum()
    total_customers = business_data['customers'].sum()
    avg_satisfaction = product_data['satisfaction'].mean()
    
    print(f"💰 Total Revenue: ${total_revenue:,}")
    print(f"👥 Total Customers: {total_customers:,}")
    print(f"⭐ Avg Satisfaction: {avg_satisfaction:.1f}/5.0")
    print()
    
    # Create dashboard with multiple charts
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            '📈 Monthly Revenue Trend',
            '👥 Customer Growth',
            '🥧 Product Users',
            '⭐ Product Satisfaction'
        ],
        specs=[
            [{"type": "scatter"}, {"type": "scatter"}],
            [{"type": "domain"}, {"type": "bar"}]
        ]
    )
    
    # 1. Revenue trend
    fig.add_trace(
        go.Scatter(
            x=business_data['month'],
            y=business_data['revenue'],
            mode='lines+markers',
            name='Revenue',
            line=dict(color='#2E8B57', width=3)
        ),
        row=1, col=1
    )
    
    # 2. Customer growth
    fig.add_trace(
        go.Scatter(
            x=business_data['month'],
            y=business_data['customers'],
            mode='lines+markers',
            name='Customers',
            line=dict(color='#4169E1', width=3),
            fill='tonexty'
        ),
        row=1, col=2
    )
    
    # 3. Product users pie chart
    fig.add_trace(
        go.Pie(
            labels=product_data['product'],
            values=product_data['users'],
            name='Users'
        ),
        row=2, col=1
    )
    
    # 4. Product satisfaction
    fig.add_trace(
        go.Bar(
            x=product_data['product'],
            y=product_data['satisfaction'],
            name='Satisfaction',
            marker=dict(color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4'])
        ),
        row=2, col=2
    )
    
    # Update layout
    fig.update_layout(
        title='🏠 Lakehouse Analytics Dashboard',
        height=800,
        showlegend=False
    )
    
    print("🎨 Displaying dashboard...")
    fig.show()
    
    print("\n✅ Dashboard displayed successfully!")
    return fig

def main():
    """Main function"""
    print("🚀 SIMPLE WORKING DASHBOARD")
    print("=" * 50)
    print("This creates interactive charts that work in Jupyter!")
    print()
    
    try:
        fig = display_dashboard()
        
        print("\n🎉 SUCCESS!")
        print("=" * 30)
        print("✅ Interactive dashboard created")
        print("✅ Charts are fully functional")  
        print("✅ Hover for details, zoom, pan")
        print("✅ No network issues")
        print("✅ Works in any Jupyter environment")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()