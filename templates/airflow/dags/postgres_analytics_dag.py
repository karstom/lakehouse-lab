                result = conn.execute("""
                    SELECT 
                        product_category,
                        COUNT(*) as order_count,
                        SUM(total_amount) as total_revenue,
                        AVG(total_amount) as avg_order_value
                    FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
                    GROUP BY product_category
                    ORDER BY total_revenue DESC
                """).fetchall()
                
                logging.info("✅ Product category analysis:")
                for row in result:
                    logging.info(f"  📊 {row[0]}: {row[1]} orders, ${row[2]:.2f} revenue, ${row[3]:.2f} avg")
                
                return len(result)
            else:
                logging.info("ℹ️ No data to transform")
                return 0
                
        except Exception as e:
            logging.error(f"❌ Transformation failed: {e}")
            raise
            
    finally:
        conn.close()

def data_quality_check(**context):
    """Run basic data quality checks"""
    import duckdb
    
    conn = duckdb.connect()
    
    try:
        # Configure S3 access
        conn.execute("INSTALL httpfs")
        conn.execute("LOAD httpfs")
        conn.execute("SET s3_endpoint='minio:9000'")
        conn.execute("SET s3_access_key_id='minio'")
        conn.execute("SET s3_secret_access_key='minio123'")
        conn.execute("SET s3_use_ssl=false")
        conn.execute("SET s3_url_style='path'")
        
        try:
            # Basic quality checks
            checks = [
                ("Record Count", "SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')"),
                ("Null Check", "SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') WHERE order_id IS NULL"),
                ("Date Range", "SELECT MIN(order_date), MAX(order_date) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')"),
            ]
            
            results = {}
            for check_name, query in checks:
                try:
                    result = conn.execute(query).fetchone()
                    results[check_name] = result
                    logging.info(f"✅ {check_name}: {result}")
                except Exception as e:
                    logging.warning(f"⚠️ {check_name}: Could not execute - {e}")
                    results[check_name] = f"ERROR: {e}"
            
            return results
            
        except Exception as e:
            logging.warning(f"⚠️ Quality checks could not complete: {e}")
            return {"status": "skipped", "reason": str(e)}
            
    finally:
        conn.close()

# Define tasks
check_deps = PythonOperator(
    task_id='check_dependencies',
    python_callable=check_dependencies,
    dag=dag,
)

configure_s3 = PythonOperator(
    task_id='configure_s3',
    python_callable=configure_duckdb_s3,
    dag=dag,
)

extract_task = PythonOperator(
    task_id='extract_data',
    python_callable=extract_data,
    dag=dag,
)

transform_task = PythonOperator(
    task_id='transform_data',
    python_callable=transform_data,
    dag=dag,
)
