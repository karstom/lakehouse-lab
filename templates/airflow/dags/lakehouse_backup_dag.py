"""
Lakehouse Lab Backup DAG

This DAG runs automated backups of the Lakehouse Lab stack using the
backup-lakehouse.sh script. It can be scheduled to run daily, weekly,
or on any custom schedule.

Configuration:
- Modify the schedule_interval for your backup frequency
- Adjust backup_options for compression, retention, etc.
- Set LAKEHOUSE_BACKUP_PATH environment variable if needed
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.python_operator import PythonOperator
from airflow.operators.email_operator import EmailOperator
from airflow.utils.dates import days_ago
from airflow.hooks.base_hook import BaseHook
import os

# Default arguments for the DAG
default_args = {
    'owner': 'lakehouse-admin',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'catchup': False
}

# DAG configuration
DAG_ID = 'lakehouse_backup'
SCHEDULE_INTERVAL = '0 2 * * *'  # Daily at 2 AM
BACKUP_RETENTION_DAYS = 30
ENABLE_COMPRESSION = True
ENABLE_VERIFICATION = True

# Environment configuration
LAKEHOUSE_PATH = os.getenv('LAKEHOUSE_PATH', '/opt/lakehouse-lab')
BACKUP_OUTPUT_DIR = os.getenv('LAKEHOUSE_BACKUP_PATH', f'{LAKEHOUSE_PATH}/backups')
NOTIFICATION_EMAIL = os.getenv('BACKUP_NOTIFICATION_EMAIL', '')

# Create the DAG
dag = DAG(
    DAG_ID,
    default_args=default_args,
    description='Automated Lakehouse Lab backup system',
    schedule_interval=SCHEDULE_INTERVAL,
    max_active_runs=1,  # Prevent overlapping backups
    tags=['backup', 'lakehouse', 'maintenance']
)

def prepare_backup_environment(**context):
    """
    Prepare the environment and validate prerequisites for backup
    """
    import logging
    import subprocess
    import json
    
    logger = logging.getLogger(__name__)
    
    # Check available disk space
    result = subprocess.run(['df', '-h', BACKUP_OUTPUT_DIR], 
                          capture_output=True, text=True)
    logger.info(f"Disk space for backups:\n{result.stdout}")
    
    # Check Docker services status
    result = subprocess.run(['docker', 'compose', 'ps', '--format', 'json'], 
                          cwd=LAKEHOUSE_PATH, capture_output=True, text=True)
    if result.returncode == 0:
        services = json.loads(result.stdout) if result.stdout.strip() else []
        running_services = [s for s in services if 'running' in s.get('State', '').lower()]
        logger.info(f"Running services: {len(running_services)}")
        
        # Store service status for use in other tasks
        return {
            'running_services': len(running_services),
            'total_services': len(services),
            'disk_info': result.stdout
        }
    else:
        logger.warning("Could not check Docker service status")
        return {'running_services': 0, 'total_services': 0}

def generate_backup_options(**context):
    """
    Generate backup command options based on configuration
    """
    options = [
        f'--output-dir {BACKUP_OUTPUT_DIR}',
        f'--retention-days {BACKUP_RETENTION_DAYS}'
    ]
    
    if ENABLE_COMPRESSION:
        options.append('--compress')
    
    if ENABLE_VERIFICATION:
        options.append('--verify')
    
    # Use parallel processing if multiple services are running
    task_instance = context['task_instance']
    prep_data = task_instance.xcom_pull(task_ids='prepare_backup')
    if prep_data and prep_data.get('running_services', 0) > 3:
        options.append('--parallel')
    
    return ' '.join(options)

# Task 1: Prepare backup environment
prepare_task = PythonOperator(
    task_id='prepare_backup',
    python_callable=prepare_backup_environment,
    dag=dag
)

# Task 2: Generate backup options
options_task = PythonOperator(
    task_id='generate_backup_options',
    python_callable=generate_backup_options,
    dag=dag
)

# Task 3: Run the actual backup
backup_task = BashOperator(
    task_id='run_backup',
    bash_command='''
        cd {{ params.lakehouse_path }} && \
        ./scripts/backup-lakehouse.sh {{ task_instance.xcom_pull(task_ids='generate_backup_options') }}
    ''',
    params={
        'lakehouse_path': LAKEHOUSE_PATH
    },
    dag=dag
)

# Task 4: Verify backup completion
verify_task = BashOperator(
    task_id='verify_backup',
    bash_command='''
        # Get the latest backup directory
        LATEST_BACKUP=$(find {{ params.backup_dir }} -maxdepth 1 -type d -name "lakehouse-backup-*" | sort | tail -1)
        
        if [[ -z "$LATEST_BACKUP" ]]; then
            echo "ERROR: No backup found"
            exit 1
        fi
        
        echo "Latest backup: $LATEST_BACKUP"
        
        # Check if backup metadata exists
        if [[ -f "$LATEST_BACKUP/backup-metadata.json" ]]; then
            echo "✅ Backup metadata found"
            cat "$LATEST_BACKUP/backup-metadata.json" | python -m json.tool
        else
            echo "⚠️  Backup metadata missing"
        fi
        
        # Check backup size
        BACKUP_SIZE=$(du -sh "$LATEST_BACKUP" | cut -f1)
        echo "📊 Backup size: $BACKUP_SIZE"
        
        # Verify minimum expected files exist
        FILE_COUNT=$(find "$LATEST_BACKUP" -type f | wc -l)
        if [[ $FILE_COUNT -lt 5 ]]; then
            echo "⚠️  Backup may be incomplete (only $FILE_COUNT files)"
            exit 1
        else
            echo "✅ Backup appears complete ($FILE_COUNT files)"
        fi
    ''',
    params={
        'backup_dir': BACKUP_OUTPUT_DIR
    },
    dag=dag
)

# Task 5: Send notification email (if configured)
def send_backup_notification(**context):
    """
    Send backup completion notification
    """
    if not NOTIFICATION_EMAIL:
        return "No notification email configured"
    
    task_instance = context['task_instance']
    backup_output = task_instance.xcom_pull(task_ids='run_backup')
    verify_output = task_instance.xcom_pull(task_ids='verify_backup')
    
    # Extract backup information
    backup_lines = backup_output.split('\n') if backup_output else []
    backup_info = [line for line in backup_lines if 'Backup ID:' in line or 'Total size:' in line or 'Files backed up:' in line]
    
    subject = f"Lakehouse Lab Backup Completed - {datetime.now().strftime('%Y-%m-%d')}"
    
    body = f"""
    Lakehouse Lab Backup Completed Successfully
    
    Execution Date: {context['ds']}
    DAG Run ID: {context['run_id']}
    
    Backup Information:
    {chr(10).join(backup_info) if backup_info else 'Backup completed'}
    
    Verification Results:
    {verify_output if verify_output else 'Verification completed'}
    
    Backup Location: {BACKUP_OUTPUT_DIR}
    
    You can view detailed logs in the Airflow UI.
    """
    
    # Use Airflow's email functionality
    from airflow.utils.email import send_email
    send_email(
        to=[NOTIFICATION_EMAIL],
        subject=subject,
        html_content=body.replace('\n', '<br>\n')
    )
    
    return f"Notification sent to {NOTIFICATION_EMAIL}"

notification_task = PythonOperator(
    task_id='send_notification',
    python_callable=send_backup_notification,
    trigger_rule='all_done',  # Run even if backup fails
    dag=dag
)

# Task 6: Cleanup old backup logs (optional)
cleanup_task = BashOperator(
    task_id='cleanup_old_logs',
    bash_command='''
        # Clean up Airflow logs older than retention period
        find /opt/airflow/logs -type f -name "*.log" -mtime +{{ params.retention_days }} -delete 2>/dev/null || true
        
        echo "Log cleanup completed"
    ''',
    params={
        'retention_days': BACKUP_RETENTION_DAYS
    },
    trigger_rule='all_success',
    dag=dag
)

# Define task dependencies
prepare_task >> options_task >> backup_task >> verify_task >> [notification_task, cleanup_task]

# Add documentation
dag.doc_md = """
# Lakehouse Lab Backup DAG

This DAG performs automated backups of the Lakehouse Lab stack components:

## What Gets Backed Up
- **PostgreSQL**: Full database dumps
- **MinIO**: All buckets and object storage data
- **Jupyter**: Notebooks and configuration
- **Airflow**: DAGs, logs, and plugins  
- **Spark**: Jobs and execution logs
- **Superset**: Dashboards and configuration
- **Other Services**: Homer, Vizro, LanceDB, etc.

## Configuration
You can customize the backup behavior by modifying the variables at the top of this DAG:

- `SCHEDULE_INTERVAL`: When to run backups (cron format)
- `BACKUP_RETENTION_DAYS`: How long to keep backups
- `ENABLE_COMPRESSION`: Whether to compress backups
- `ENABLE_VERIFICATION`: Whether to verify backup integrity

## Environment Variables
- `LAKEHOUSE_PATH`: Path to Lakehouse Lab installation
- `LAKEHOUSE_BACKUP_PATH`: Where to store backups
- `BACKUP_NOTIFICATION_EMAIL`: Email for notifications

## Monitoring
The DAG includes verification steps and can send email notifications on completion or failure.
Monitor backup sizes and completion times through the Airflow UI.

## Manual Execution
You can also run backups manually using:
```bash
cd /path/to/lakehouse-lab
./scripts/backup-lakehouse.sh --compress --verify
```
"""