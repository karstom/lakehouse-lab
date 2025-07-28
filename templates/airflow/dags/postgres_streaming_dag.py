"""
PostgreSQL Streaming DAG
Demonstrates streaming data processing with PostgreSQL for Lakehouse Lab
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
import logging

default_args = {
    'owner': 'lakehouse-lab',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

dag = DAG(
    'postgres_streaming_dag',
    default_args=default_args,
    description='PostgreSQL streaming data processing pipeline',
    schedule_interval=timedelta(hours=4),
    catchup=False,
    tags=['postgresql', 'streaming', 'real-time']
)

def simulate_streaming_data(**context):
    """Simulate streaming data ingestion to PostgreSQL"""
    try:
        import psycopg2
        from datetime import datetime
        import random
        
        conn_params = {
            'host': 'postgres',
            'port': 5432,
            'database': 'lakehouse',
            'user': 'postgres',
            'password': 'postgres'
        }
        
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        # Create streaming events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS streaming_events (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(50),
                event_data JSONB,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Simulate some streaming events
        event_types = ['user_login', 'page_view', 'purchase', 'search']
        
        for i in range(10):
            event_type = random.choice(event_types)
            event_data = {
                'user_id': random.randint(1, 1000),
                'session_id': f"session_{random.randint(1, 100)}",
                'value': random.uniform(1.0, 100.0)
            }
            
            cursor.execute("""
                INSERT INTO streaming_events (event_type, event_data) 
                VALUES (%s, %s)
            """, (event_type, psycopg2.extras.Json(event_data)))
        
        # Get streaming statistics
        cursor.execute("""
            SELECT event_type, COUNT(*) as event_count 
            FROM streaming_events 
            WHERE timestamp >= NOW() - INTERVAL '1 day'
            GROUP BY event_type
            ORDER BY event_count DESC
        """)
        
        results = cursor.fetchall()
        logging.info("📊 Streaming Events (last 24h):")
        for event_type, count in results:
            logging.info(f"   {event_type}: {count} events")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info("✅ Streaming data simulation completed")
        return "streaming_completed"
        
    except Exception as e:
        logging.error(f"❌ Streaming simulation failed: {e}")
        return "streaming_failed"

def process_streaming_analytics(**context):
    """Process streaming analytics"""
    try:
        import psycopg2
        
        conn_params = {
            'host': 'postgres',
            'port': 5432,
            'database': 'lakehouse',
            'user': 'postgres',
            'password': 'postgres'
        }
        
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        # Create analytics summary table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS streaming_analytics (
                id SERIAL PRIMARY KEY,
                analysis_date DATE DEFAULT CURRENT_DATE,
                total_events INTEGER,
                unique_users INTEGER,
                avg_session_events DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Calculate analytics from streaming events
        cursor.execute("""
            WITH daily_stats AS (
                SELECT 
                    COUNT(*) as total_events,
                    COUNT(DISTINCT (event_data->>'user_id')::int) as unique_users,
                    AVG(CASE WHEN (event_data->>'session_id') IS NOT NULL 
                        THEN 1.0 ELSE 0.0 END) as avg_session_events
                FROM streaming_events 
                WHERE DATE(timestamp) = CURRENT_DATE
            )
            INSERT INTO streaming_analytics (total_events, unique_users, avg_session_events)
            SELECT total_events, unique_users, avg_session_events 
            FROM daily_stats
            WHERE total_events > 0
        """)
        
        # Get latest analytics
        cursor.execute("""
            SELECT total_events, unique_users, avg_session_events 
            FROM streaming_analytics 
            WHERE analysis_date = CURRENT_DATE
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        if result:
            total, users, avg_events = result
            logging.info(f"📈 Today's Analytics: {total} events, {users} users, {avg_events:.2f} avg events")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return "analytics_processed"
        
    except Exception as e:
        logging.error(f"❌ Streaming analytics failed: {e}")
        return "analytics_failed"

# Define tasks
simulate_task = PythonOperator(
    task_id='simulate_streaming_data',
    python_callable=simulate_streaming_data,
    dag=dag
)

analytics_task = PythonOperator(
    task_id='process_streaming_analytics',
    python_callable=process_streaming_analytics,
    dag=dag
)

# Set dependencies
simulate_task >> analytics_task