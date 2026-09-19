import functions_framework
from google.cloud import bigquery

@functions_framework.http
def run_daily_snapshot_model_retrain(request):
    try:
        client = bigquery.Client()

        # Step 1: Append data to time series table
        insert_query = """
            INSERT INTO `co2ops-460813.gcp_server_details.server_metrics_timeseries` (
            date, instance_id, instance_type, region,
            cpu_util, memory_util, disk_iops, network_iops, total_carbon
            )
            SELECT
            TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), DAY) AS date,
            Instance_ID,
            Instance_Type,
            Region,

            ROUND(
                CASE MOD(FARM_FINGERPRINT(Instance_ID), 4)
                WHEN 0 THEN Average_CPU_Utilization * (1 + RAND() * 0.1)
                WHEN 1 THEN Average_CPU_Utilization * (1 - RAND() * 0.1)
                WHEN 2 THEN Average_CPU_Utilization + RAND() * 5
                ELSE Average_CPU_Utilization - RAND() * 5
                END, 2) AS cpu_util,

            ROUND(
                CASE MOD(FARM_FINGERPRINT(Instance_ID), 3)
                WHEN 0 THEN Memory_Utilization * (1 + RAND() * 0.2)
                WHEN 1 THEN Memory_Utilization * (1 - RAND() * 0.15)
                ELSE Memory_Utilization + RAND() * 10
                END, 2) AS memory_util,

            CAST(
                CASE MOD(FARM_FINGERPRINT(Instance_ID), 3)
                WHEN 0 THEN Disk_IOPS + CAST(FLOOR(RAND() * 50) AS INT64)
                WHEN 1 THEN Disk_IOPS - CAST(FLOOR(RAND() * 30) AS INT64)
                ELSE Disk_IOPS
                END AS INT64) AS disk_iops,

            CAST(
                CASE MOD(FARM_FINGERPRINT(Instance_ID), 3)
                WHEN 0 THEN Network_IOPS + CAST(FLOOR(RAND() * 40) AS INT64)
                WHEN 1 THEN Network_IOPS - CAST(FLOOR(RAND() * 20) AS INT64)
                ELSE Network_IOPS
                END AS INT64) AS network_iops,

            ROUND(
                CASE MOD(FARM_FINGERPRINT(Instance_ID), 4)
                WHEN 0 THEN Total_Carbon_Emission_in_kg * (1 + RAND() * 0.2)
                WHEN 1 THEN Total_Carbon_Emission_in_kg * (1 - RAND() * 0.1)
                WHEN 2 THEN Total_Carbon_Emission_in_kg + RAND() * 0.5
                ELSE Total_Carbon_Emission_in_kg
                END, 3) AS total_carbon

            FROM `co2ops-460813.gcp_server_details.server_metrics`
            """
        client.query(insert_query).result()


        # Step 2: Create/Replace Forecast Models
        model_specs = [
            ("server_cpu_forecast_model", "cpu_util"),
            ("server_mem_forecast_model", "memory_util"),
            ("server_carbon_forecast_model", "total_carbon")
        ]

        for model_name, column in model_specs:
            create_model_query = f"""
            CREATE OR REPLACE MODEL `co2ops-460813.gcp_server_details.{model_name}`
            OPTIONS(
            MODEL_TYPE='ARIMA_PLUS',
            TIME_SERIES_TIMESTAMP_COL='date',
            TIME_SERIES_ID_COL='Instance_ID',
            TIME_SERIES_DATA_COL='{column}',
            DATA_FREQUENCY='AUTO_FREQUENCY'
            ) AS
            SELECT
            date,
            Instance_ID,
            {column}
            FROM
            `co2ops-460813.gcp_server_details.server_metrics_timeseries`
            WHERE {column} IS NOT NULL
            """
            client.query(create_model_query).result()
        
    except Exception as e:
        return "❌ Error occurred: " + str(e)

    return "Success"
