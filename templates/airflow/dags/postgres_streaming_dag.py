            ("Date Range", "SELECT MIN(order_date), MAX(order_date) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')"),
            ("Negative Amounts", "SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') WHERE total_amount < 0"),
            ("Duplicate Orders", "SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')"),
            ("Category Distribution", "SELECT product_category, COUNT(*) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') GROUP BY product_category"),
        ]
        
        results = {}
        failed_checks = 0
        
        for check_name, query in checks:
            try:
                result = conn.execute(query).fetchall()
                results[check_name] = result
                
                # Define quality rules
                if check_name == "Record Count" and (not result or result[0][0] == 0):
                    logging.warning(f"⚠️ {check_name}: No data found")
                    failed_checks += 1
                elif check_name in ["Null Check - Order ID", "Null Check - Customer ID", "Negative Amounts", "Duplicate Orders"] and result and result[0][0] > 0:
                    logging.warning(f"⚠️ {check_name}: Found {result[0][0]} issues")
                    failed_checks += 1
                else:
                    logging.info(f"✅ {check_name}: {result}")
                    
            except Exception as e:
                logging.error(f"❌ {check_name}: ERROR - {e}")
                results[check_name] = f"ERROR: {e}"
                failed_checks += 1
        
        # Summary
        total_checks = len(checks)
        passed_checks = total_checks - failed_checks
        
        logging.info(f"📊 Quality Check Summary: {passed_checks}/{total_checks} checks passed")
        
        if failed_checks > 0:
            logging.warning(f"⚠️ {failed_checks} quality issues detected")
        else:
            logging.info("✅ All quality checks passed!")
        
        return results
        
    except ImportError as e:
        logging.error(f"❌ Missing dependency: {e}")
        raise
    finally:
        conn.close()

quality_check_task = PythonOperator(
    task_id='run_comprehensive_quality_checks',
    python_callable=run_comprehensive_quality_checks,
    dag=dag,
