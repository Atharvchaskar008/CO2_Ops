import logging
import os
import re
from typing import List, Dict, Any, Optional
import pandas as pd
import duckdb

from co2ops_agent.bedrock.agent import BedrockAgent
from co2ops_agent.bedrock.state import CO2OpsState

logger = logging.getLogger(__name__)

# Default benchmark AWS EC2 infrastructure dataset for rightsizing analysis & demos
DEFAULT_AWS_SERVERS = [
    {
        "Instance_ID": "i-01a2b3c4d5e6f7g80",
        "Instance_Type": "m5.2xlarge",
        "Region": "us-east-1",
        "Average_CPU_Utilization": 14.5,
        "Memory_Utilization": 32.0,
        "Disk_IOPS": 120,
        "Network_IOPS": 250,
        "Total_Carbon_Emission_in_kg": 2.850,
        "provenance": "demo",
        "telemetry_source": "demo",
        "telemetry_verified": False,
        "is_synthetic": True,
        "telemetry_missing": False,
        "telemetry_status": "demo_data"
    },
    {
        "Instance_ID": "i-02b3c4d5e6f7g8h91",
        "Instance_Type": "c5.xlarge",
        "Region": "us-east-1",
        "Average_CPU_Utilization": 18.2,
        "Memory_Utilization": 28.5,
        "Disk_IOPS": 95,
        "Network_IOPS": 180,
        "Total_Carbon_Emission_in_kg": 1.420,
        "provenance": "demo",
        "telemetry_source": "demo",
        "telemetry_verified": False,
        "is_synthetic": True,
        "telemetry_missing": False,
        "telemetry_status": "demo_data"
    },
    {
        "Instance_ID": "i-03c4d5e6f7g8h9i02",
        "Instance_Type": "t3.large",
        "Region": "us-east-1",
        "Average_CPU_Utilization": 11.0,
        "Memory_Utilization": 25.0,
        "Disk_IOPS": 40,
        "Network_IOPS": 80,
        "Total_Carbon_Emission_in_kg": 0.650,
        "provenance": "demo",
        "telemetry_source": "demo",
        "telemetry_verified": False,
        "is_synthetic": True,
        "telemetry_missing": False,
        "telemetry_status": "demo_data"
    },
    {
        "Instance_ID": "i-04d5e6f7g8h9i0j13",
        "Instance_Type": "r5.2xlarge",
        "Region": "us-east-1",
        "Average_CPU_Utilization": 22.0,
        "Memory_Utilization": 38.0,
        "Disk_IOPS": 310,
        "Network_IOPS": 420,
        "Total_Carbon_Emission_in_kg": 3.100,
        "provenance": "demo",
        "telemetry_source": "demo",
        "telemetry_verified": False,
        "is_synthetic": True,
        "telemetry_missing": False,
        "telemetry_status": "demo_data"
    },
    {
        "Instance_ID": "i-05e6f7g8h9i0j1k24",
        "Instance_Type": "m5.xlarge",
        "Region": "us-west-2",
        "Average_CPU_Utilization": 16.4,
        "Memory_Utilization": 35.0,
        "Disk_IOPS": 150,
        "Network_IOPS": 210,
        "Total_Carbon_Emission_in_kg": 0.950,
        "provenance": "demo",
        "telemetry_source": "demo",
        "telemetry_verified": False,
        "is_synthetic": True,
        "telemetry_missing": False,
        "telemetry_status": "demo_data"
    },
    {
        "Instance_ID": "i-06f7g8h9i0j1k2l35",
        "Instance_Type": "c5.2xlarge",
        "Region": "us-west-2",
        "Average_CPU_Utilization": 21.0,
        "Memory_Utilization": 31.0,
        "Disk_IOPS": 260,
        "Network_IOPS": 340,
        "Total_Carbon_Emission_in_kg": 1.800,
        "provenance": "demo",
        "telemetry_source": "demo",
        "telemetry_verified": False,
        "is_synthetic": True,
        "telemetry_missing": False,
        "telemetry_status": "demo_data"
    },
    {
        "Instance_ID": "i-07g8h9i0j1k2l3m46",
        "Instance_Type": "m5.4xlarge",
        "Region": "eu-west-1",
        "Average_CPU_Utilization": 12.8,
        "Memory_Utilization": 29.0,
        "Disk_IOPS": 420,
        "Network_IOPS": 510,
        "Total_Carbon_Emission_in_kg": 4.200,
        "provenance": "demo",
        "telemetry_source": "demo",
        "telemetry_verified": False,
        "is_synthetic": True,
        "telemetry_missing": False,
        "telemetry_status": "demo_data"
    },
    {
        "Instance_ID": "i-08h9i0j1k2l3m4n57",
        "Instance_Type": "t3.xlarge",
        "Region": "eu-west-1",
        "Average_CPU_Utilization": 15.0,
        "Memory_Utilization": 33.0,
        "Disk_IOPS": 80,
        "Network_IOPS": 120,
        "Total_Carbon_Emission_in_kg": 1.100,
        "provenance": "demo",
        "telemetry_source": "demo",
        "telemetry_verified": False,
        "is_synthetic": True,
        "telemetry_missing": False,
        "telemetry_status": "demo_data"
    },
    {
        "Instance_ID": "i-09i0j1k2l3m4n5o68",
        "Instance_Type": "c5.xlarge",
        "Region": "ap-south-1",
        "Average_CPU_Utilization": 19.5,
        "Memory_Utilization": 34.0,
        "Disk_IOPS": 110,
        "Network_IOPS": 190,
        "Total_Carbon_Emission_in_kg": 2.450,
        "provenance": "demo",
        "telemetry_source": "demo",
        "telemetry_verified": False,
        "is_synthetic": True,
        "telemetry_missing": False,
        "telemetry_status": "demo_data"
    },
    {
        "Instance_ID": "i-10j1k2l3m4n5o6p79",
        "Instance_Type": "r5.xlarge",
        "Region": "ap-south-1",
        "Average_CPU_Utilization": 17.0,
        "Memory_Utilization": 30.0,
        "Disk_IOPS": 190,
        "Network_IOPS": 280,
        "Total_Carbon_Emission_in_kg": 2.900,
        "provenance": "demo",
        "telemetry_source": "demo",
        "telemetry_verified": False,
        "is_synthetic": True,
        "telemetry_missing": False,
        "telemetry_status": "demo_data"
    }
]


def is_demo_mode(demo_mode: Optional[bool] = None) -> bool:
    """
    Determines if CO2Ops is running in DEMO_MODE.
    Resolution priority:
    1. Explicit parameter `demo_mode` if provided.
    2. DEMO_MODE environment variable ('true', '1', 'yes' -> True; 'false', '0', 'no' -> False).
    3. Defaults to True for safe local demonstrations.
    """
    if demo_mode is not None:
        return bool(demo_mode)
    env = os.getenv("DEMO_MODE")
    if env is not None:
        return env.strip().lower() in ("true", "1", "yes")
    return True


def fetch_cloudwatch_instance_cpu(
    instance_id: str,
    region: str = "us-east-1",
    client: Optional[Any] = None,
    period: int = 3600,
    days: int = 14
) -> Optional[float]:
    """
    Fetches actual average CPU utilization for an EC2 instance from AWS CloudWatch.
    Returns:
        float: the average CPU utilization percentage over the period if data exists.
        None: if no datapoints exist in CloudWatch (explicit insufficient data).
    """
    try:
        import boto3
        from datetime import datetime, timezone, timedelta

        cw = client or boto3.client("cloudwatch", region_name=region)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)

        response = cw.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=["Average"]
        )
        datapoints = response.get("Datapoints", [])
        if not datapoints:
            logger.info(f"CloudWatch returned 0 datapoints for {instance_id} in {region}")
            return None

        avg_cpu = sum(dp["Average"] for dp in datapoints) / len(datapoints)
        return round(float(avg_cpu), 2)
    except Exception as e:
        logger.warning(f"Error fetching CloudWatch CPU for {instance_id}: {e}")
        return None


def estimate_instance_carbon_emission(instance_type: str, region: str = "us-east-1", duration_hours: float = 24.0) -> float:
    """Estimates 24-hour carbon emissions in kg for an EC2 instance based on instance type and region."""
    size = instance_type.split(".")[-1] if "." in instance_type else "large"
    watts_map = {"nano": 15, "micro": 25, "small": 40, "medium": 60, "large": 80, "xlarge": 160, "2xlarge": 320, "4xlarge": 640}
    watts = watts_map.get(size, 80)
    if "g." in instance_type:
        watts *= 0.70
    kwh = (watts * duration_hours) / 1000.0
    intensity_map = {
        "us-east-1": 0.000379,
        "us-west-2": 0.000185,
        "eu-west-1": 0.000275,
        "ap-south-1": 0.000690,
    }
    intensity = intensity_map.get(region, 0.00035)
    operational_co2 = kwh * intensity
    embodied_co2 = 0.0025 * (watts / 50.0) * (duration_hours / 24.0)
    return round(operational_co2 + embodied_co2, 3)


def get_server_dataframe(region: Optional[str] = None, demo_mode: Optional[bool] = None) -> pd.DataFrame:
    """
    Returns the server metrics DataFrame.
    Strict separation between DEMO_MODE and LIVE AWS mode:
    - In DEMO_MODE: Returns DEFAULT_AWS_SERVERS benchmark records with 'demo' provenance.
      Never queries AWS EC2 or CloudWatch.
    - In LIVE mode: Queries AWS EC2 and CloudWatch. NEVER mixes in demo instances.
      Retrieves real CPU utilization from CloudWatch; if unavailable, sets Average_CPU_Utilization to None
      and marks provenance as 'unverified_live' / 'insufficient_data'.
    """
    columns = [
        "Instance_ID", "Instance_Type", "Region", "Average_CPU_Utilization",
        "Memory_Utilization", "Disk_IOPS", "Network_IOPS", "Total_Carbon_Emission_in_kg",
        "provenance", "telemetry_source", "telemetry_verified", "is_synthetic",
        "telemetry_missing", "telemetry_status"
    ]

    if is_demo_mode(demo_mode):
        logger.info("DEMO_MODE active: returning benchmark AWS EC2 servers.")
        demo_rows = []
        for s in DEFAULT_AWS_SERVERS:
            row = dict(s)
            demo_rows.append(row)
        return pd.DataFrame(demo_rows)

    # LIVE AWS MODE:
    # In LIVE mode, NEVER mix demo/hardcoded instances with real EC2 instances.
    logger.info("LIVE AWS MODE active: querying live EC2 instances and CloudWatch metrics.")
    servers = []
    target_region = region or os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION", "us-east-1"))

    try:
        import boto3
        ec2 = boto3.client("ec2", region_name=target_region)
        cw = boto3.client("cloudwatch", region_name=target_region)

        resp = ec2.describe_instances()
        for res in resp.get("Reservations", []):
            for inst in res.get("Instances", []):
                state_name = inst.get("State", {}).get("Name")
                if state_name == "running":
                    inst_id = inst.get("InstanceId")
                    inst_type = inst.get("InstanceType", "unknown")

                    # Fetch real CloudWatch CPU utilization
                    cpu_util = fetch_cloudwatch_instance_cpu(inst_id, region=target_region, client=cw)

                    if cpu_util is not None:
                        servers.append({
                            "Instance_ID": inst_id,
                            "Instance_Type": inst_type,
                            "Region": target_region,
                            "Average_CPU_Utilization": cpu_util,
                            "Memory_Utilization": None,
                            "Disk_IOPS": 0,
                            "Network_IOPS": 0,
                            "Total_Carbon_Emission_in_kg": estimate_instance_carbon_emission(inst_type, target_region),
                            "provenance": "verified_live",
                            "telemetry_source": "cloudwatch",
                            "telemetry_verified": True,
                            "is_synthetic": False,
                            "telemetry_missing": False,
                            "telemetry_status": "sufficient_data"
                        })
                    else:
                        # Explicit insufficient data / missing CloudWatch data (no hardcoded CPU)
                        servers.append({
                            "Instance_ID": inst_id,
                            "Instance_Type": inst_type,
                            "Region": target_region,
                            "Average_CPU_Utilization": None,
                            "Memory_Utilization": None,
                            "Disk_IOPS": 0,
                            "Network_IOPS": 0,
                            "Total_Carbon_Emission_in_kg": 0.0,
                            "provenance": "unverified_live",
                            "telemetry_source": "none",
                            "telemetry_verified": False,
                            "is_synthetic": False,
                            "telemetry_missing": True,
                            "telemetry_status": "insufficient_data"
                        })
    except Exception as e:
        logger.error(f"Live AWS EC2 telemetry retrieval error: {e}")

    if not servers:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(servers)


def execute_server_query(
    sql: str,
    state: Optional[CO2OpsState] = None,
    demo_mode: Optional[bool] = None,
    region: Optional[str] = None
) -> dict:
    """
    Executes a SQL query against the AWS EC2 server metrics table using DuckDB.
    Maintains strict DEMO_MODE vs LIVE mode separation, attaches provenance metadata,
    and automatically populates state.infra_data and state.custom_metadata.
    """
    try:
        logger.info(f"Executing SQL via DuckDB: {sql}")
        target_region = region
        target_demo_mode = demo_mode
        if state is not None:
            if target_region is None and state.region:
                target_region = state.region
            if target_demo_mode is None and "demo_mode" in state.custom_metadata:
                target_demo_mode = state.custom_metadata["demo_mode"]

        df = get_server_dataframe(region=target_region, demo_mode=target_demo_mode)

        if df.empty:
            error_msg = "No live EC2 instances found in AWS account" if not is_demo_mode(target_demo_mode) else "No matching records found"
            if state is not None:
                state.infra_data = []
                state.custom_metadata["telemetry_provenance"] = "none"
                state.custom_metadata["missing_telemetry"] = True
                state.custom_metadata["telemetry_status"] = "insufficient_data"
            return {"status": "error", "error_message": error_msg, "rows": [], "row_count": 0}

        con = duckdb.connect()
        con.register("server_metrics", df)
        con.register("aws_server_metrics", df)
        con.register("gcp_server_details.server_metrics", df)

        clean_sql = re.sub(r'`[^`]*\.gcp_server_details\.server_metrics`', 'server_metrics', sql)
        clean_sql = re.sub(r'`server_metrics`', 'server_metrics', clean_sql)

        result_df = con.execute(clean_sql).df()
        data = result_df.to_dict(orient="records")

        if not data:
            return {"status": "error", "error_message": "No matching records found", "rows": [], "row_count": 0}

        # Provenance attribution: ensure each record maintains its source provenance
        df_prov_map = {}
        for _, r in df.iterrows():
            inst_id = str(r["Instance_ID"])
            df_prov_map[inst_id] = {
                "provenance": r.get("provenance"),
                "telemetry_source": r.get("telemetry_source"),
                "telemetry_verified": bool(r.get("telemetry_verified", False)),
                "is_synthetic": bool(r.get("is_synthetic", False)),
                "telemetry_missing": bool(r.get("telemetry_missing", False)),
                "telemetry_status": r.get("telemetry_status")
            }

        for row in data:
            inst_id = str(row.get("Instance_ID", ""))
            if inst_id in df_prov_map:
                pinfo = df_prov_map[inst_id]
                for pk, pv in pinfo.items():
                    if pk not in row or row[pk] is None:
                        row[pk] = pv

        if state is not None:
            state.infra_data = data
            state.set("infra_data", data)

            has_missing = any(r.get("telemetry_missing") is True for r in data)
            all_verified = all(r.get("telemetry_verified") is True for r in data)
            any_synthetic = any(r.get("is_synthetic") is True for r in data)
            sources = list({str(r.get("telemetry_source", "")) for r in data})

            state.custom_metadata["telemetry_source"] = sources[0] if len(sources) == 1 else "mixed"
            state.custom_metadata["telemetry_verified"] = all_verified
            state.custom_metadata["missing_telemetry"] = has_missing
            state.custom_metadata["is_synthetic"] = any_synthetic

            if any_synthetic:
                state.custom_metadata["telemetry_provenance"] = "synthetic" if any(r.get("provenance") == "synthetic" for r in data) else "demo"
                state.custom_metadata["telemetry_status"] = "demo_data"
            elif has_missing:
                state.custom_metadata["telemetry_provenance"] = "unverified_live"
                state.custom_metadata["telemetry_status"] = "insufficient_data"
            else:
                state.custom_metadata["telemetry_provenance"] = "verified_live"
                state.custom_metadata["telemetry_status"] = "sufficient_data"

        return {
            "status": "success",
            "row_count": len(data),
            "rows": data
        }
    except Exception as e:
        logger.error(f"DuckDB query execution error: {e}")
        df = get_server_dataframe(region=region, demo_mode=demo_mode)
        data = df.to_dict(orient="records")
        if state is not None:
            state.infra_data = data
            state.set("infra_data", data)
        return {
            "status": "success",
            "row_count": len(df),
            "rows": data
        }


# Define the AWS Bedrock agent (replaces Google ADK LlmAgent)
infra_scout_agent = BedrockAgent(
    name="aws_server_analyst",
    description="Fetches AWS EC2 server metrics from the infrastructure database for downstream analysis.",
    system_instruction="""
    You are responsible for retrieving AWS EC2 server telemetry from the database table:
    `server_metrics`.

    Columns available:
    - Instance_ID
    - Instance_Type
    - Region (e.g., 'us-east-1', 'us-west-2', 'eu-west-1', 'ap-south-1')
    - Average_CPU_Utilization
    - Memory_Utilization
    - Total_Carbon_Emission_in_kg

    You must:
    1. Extract only the **filters** (such as Region, Instance_Type) from the user query.
    2. Normalize region formats (e.g. 'us_east_1' -> 'us-east-1').
    3. Ignore intent words like "optimize", "recommend", or "analyze". You do **not** provide recommendations yourself.
    4. Generate a SQL query matching those filters:
       SELECT Instance_ID, Average_CPU_Utilization, Instance_Type, Memory_Utilization, Region, Total_Carbon_Emission_in_kg 
       FROM server_metrics 
       [WHERE Region = 'us-east-1']
    5. Call the `execute_server_query` tool with the generated SQL.
    6. Return the tool result directly under the `infra_data` key.

    - If no region filter is given, return all rows.
    - Always execute the query using the `execute_server_query` tool.
    """,
    tools=[execute_server_query],
    output_state_key="infra_data"
)


