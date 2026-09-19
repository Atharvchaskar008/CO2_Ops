import os
import shutil
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
import pandas as pd
import duckdb
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from co2ops_agent.agents.forecaster_agent.agent import generate_aws_forecast
from co2ops_agent.agents.optimization_advisor_agent.sub_agents.infra_scout_agent.agent import DEFAULT_AWS_SERVERS

logger = logging.getLogger(__name__)

def generate_weekly_timeseries_df() -> pd.DataFrame:
    """
    Generates a 7-day historical time-series DataFrame for the AWS EC2 instances
    for DuckDB analytics and chart generation.
    """
    records = []
    base_date = datetime.now() - timedelta(days=7)

    for i in range(7):
        current_dt = base_date + timedelta(days=i)
        date_str = current_dt.strftime("%Y-%m-%d")
        for server in DEFAULT_AWS_SERVERS:
            # Deterministic variation
            factor = 1.0 + ((hash(f"{server['Instance_ID']}_{i}") % 20) - 10) / 100.0
            cpu = round(server["Average_CPU_Utilization"] * factor, 2)
            mem = round(server["Memory_Utilization"] * factor, 2)
            carbon = round(server["Total_Carbon_Emission_in_kg"] * factor, 3)

            records.append({
                "date": date_str,
                "instance_id": server["Instance_ID"],
                "instance_type": server["Instance_Type"],
                "region": server["Region"],
                "cpu_util": cpu,
                "memory_util": mem,
                "disk_iops": server["Disk_IOPS"],
                "network_iops": server["Network_IOPS"],
                "total_carbon": carbon
            })

    return pd.DataFrame(records)


def run_query(sql: str) -> pd.DataFrame:
    """Executes SQL over the AWS time-series DataFrame using DuckDB."""
    df_timeseries = generate_weekly_timeseries_df()
    con = duckdb.connect()
    con.register("server_metrics_timeseries", df_timeseries)
    con.register("gcp_server_details.server_metrics_timeseries", df_timeseries)

    # Sanitize query if GCP backticks exist
    clean_sql = sql.replace("`co2ops-460813.gcp_server_details.server_metrics_timeseries`", "server_metrics_timeseries")
    clean_sql = clean_sql.replace("`server_metrics_timeseries`", "server_metrics_timeseries")
    clean_sql = clean_sql.replace("DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)", f"'{((datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))}'")
    clean_sql = clean_sql.replace("DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)", f"'{((datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))}'")
    clean_sql = clean_sql.replace("CURRENT_DATE()", f"'{datetime.now().strftime('%Y-%m-%d')}'")
    clean_sql = clean_sql.replace("COUNTIF(", "COUNT(CASE WHEN ")
    clean_sql = clean_sql.replace(") * 100.0", " THEN 1 END) * 100.0")

    try:
        return con.execute(clean_sql).df()
    except Exception as e:
        logger.warning(f"DuckDB SQL fallback: {e}")
        return df_timeseries


def get_weekly_data() -> list:
    """Returns aggregated weekly metrics by EC2 instance."""
    df = generate_weekly_timeseries_df()
    agg = df.groupby(["instance_id", "instance_type", "region"]).agg({
        "cpu_util": "mean",
        "memory_util": "mean",
        "total_carbon": "sum"
    }).reset_index()

    agg.columns = ["instance_id", "instance_type", "region", "average_cpu_utilization", "average_memory_utilization", "total_carbon_emission_kg"]
    agg["average_cpu_utilization"] = agg["average_cpu_utilization"].round(2)
    agg["average_memory_utilization"] = agg["average_memory_utilization"].round(2)
    agg["total_carbon_emission_kg"] = agg["total_carbon_emission_kg"].round(3)
    return agg.to_dict("records")


def build_charts() -> dict:
    """Renders the 4 core sustainability trend charts using Matplotlib."""
    os.makedirs("charts", exist_ok=True)
    df = generate_weekly_timeseries_df()
    chart_paths = {}

    # Chart 1: Time Series - Carbon Emissions
    daily_carbon = df.groupby("date")["total_carbon"].sum().reset_index()
    path1 = "charts/chart1_timeseries.png"
    plt.figure(figsize=(10, 5))
    plt.plot(daily_carbon["date"], daily_carbon["total_carbon"], marker='o', color="#10B981", linewidth=2.5)
    plt.title("AWS Daily Carbon Emissions Trend (Last 7 Days)", fontsize=13, pad=12)
    plt.xlabel("Date")
    plt.ylabel("Total Emission (kg CO2e)")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig(path1, dpi=120)
    chart_paths['carbon_timeseries'] = path1
    plt.close()

    # Chart 2: Regional Utilization Bar Chart
    region_util = df.groupby("region").agg({"cpu_util": "mean", "memory_util": "mean"}).reset_index()
    path2 = "charts/chart2_bar.png"
    plt.figure(figsize=(10, 5))
    x_axis = range(len(region_util))
    plt.bar([i - 0.2 for i in x_axis], region_util["cpu_util"], width=0.4, label='Avg CPU (%)', color="#3B82F6")
    plt.bar([i + 0.2 for i in x_axis], region_util["memory_util"], width=0.4, label='Avg Memory (%)', color="#8B5CF6")
    plt.xticks(x_axis, region_util["region"])
    plt.title("Average AWS Resource Utilization by Region", fontsize=13, pad=12)
    plt.xlabel("AWS Region")
    plt.ylabel("Utilization (%)")
    plt.legend()
    plt.grid(axis='y', linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(path2, dpi=120)
    chart_paths['region_utilization'] = path2
    plt.close()

    # Chart 3: CPU vs Carbon Scatter Plot
    inst_summary = df.groupby("instance_id").agg({"cpu_util": "mean", "total_carbon": "sum"}).reset_index()
    path3 = "charts/chart3_scatter.png"
    plt.figure(figsize=(8, 5))
    plt.scatter(inst_summary["cpu_util"], inst_summary["total_carbon"], alpha=0.8, color="#F59E0B", s=80, edgecolors="black")
    plt.title("CPU Utilization vs Carbon Emissions per EC2 Instance", fontsize=13, pad=12)
    plt.xlabel("Average CPU Utilization (%)")
    plt.ylabel("Weekly Total Carbon (kg CO2e)")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(path3, dpi=120)
    chart_paths['cpu_vs_carbon'] = path3
    plt.close()

    # Chart 4: Underutilization Rate Area Chart
    df["underutilized"] = (df["cpu_util"] < 30.0) | (df["memory_util"] < 40.0)
    underutil_rate = df.groupby("date")["underutilized"].mean() * 100.0
    underutil_df = underutil_rate.reset_index()
    underutil_df.columns = ["date", "rate"]

    path4 = "charts/chart4_underutilization.png"
    plt.figure(figsize=(10, 5))
    plt.fill_between(underutil_df["date"], underutil_df["rate"], color="#60A5FA", alpha=0.4)
    plt.plot(underutil_df["date"], underutil_df["rate"], color="#2563EB", linewidth=2)
    plt.title("Infrastructure Under-utilization Rate Over Time", fontsize=13, pad=12)
    plt.xlabel("Date")
    plt.ylabel("Underutilized Instances (%)")
    plt.ylim(0, 100)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig(path4, dpi=120)
    chart_paths['underutilization'] = path4
    plt.close()

    return chart_paths


def upload_to_s3_or_local(local_file_path: str, bucket_name: str = "") -> str:
    """
    Uploads an asset to Amazon S3 and generates a pre-signed URL.
    Falls back to absolute local URI if S3 is not configured.
    """
    bucket = bucket_name or os.getenv("AWS_REPORTS_BUCKET", "")
    filename = os.path.basename(local_file_path)

    if bucket:
        try:
            import boto3
            region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
            s3 = boto3.client("s3", region_name=region)
            s3.upload_file(local_file_path, bucket, f"reports/{filename}")
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": f"reports/{filename}"},
                ExpiresIn=604800  # 7 days
            )
            return url
        except Exception as e:
            logger.debug(f"S3 upload fallback: {e}")

    return f"file:///{os.path.abspath(local_file_path).replace('\\', '/')}"


def create_google_doc(title: str, body_content: str, tool_context=None, state=None) -> dict:
    """
    Creates and saves the weekly sustainability report.
    Uploads charts to Amazon S3 (or local report directory), generates a clean report document,
    and returns accessible links.
    """
    logger.info(f"Generating weekly report: {title}")
    chart_paths = build_charts()

    chart_to_links = {
        "[[chart_carbon_timeseries]]": upload_to_s3_or_local(chart_paths["carbon_timeseries"]),
        "[[chart_region_utilization]]": upload_to_s3_or_local(chart_paths["region_utilization"]),
        "[[chart_cpu_vs_carbon]]": upload_to_s3_or_local(chart_paths["cpu_vs_carbon"]),
        "[[chart_underutilization]]": upload_to_s3_or_local(chart_paths["underutilization"])
    }

    # Save Markdown report locally
    os.makedirs("reports", exist_ok=True)
    clean_title = title.replace(" ", "_").replace("–", "-").replace("—", "-")
    report_file = f"reports/{clean_title}.md"

    # Replace chart placeholders with Markdown image links
    final_content = body_content
    for placeholder, link in chart_to_links.items():
        final_content = final_content.replace(placeholder, f"\n\n![Chart]({link})\n\n")

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{final_content}")

    report_url = upload_to_s3_or_local(report_file)

    if state is not None:
        if hasattr(state, "custom_metadata"):
            state.custom_metadata["chart_links"] = chart_to_links
        elif hasattr(state, "set"):
            state.set("chart_links", chart_to_links)
        elif isinstance(state, dict):
            state["chart_links"] = chart_to_links

    if tool_context is not None:
        if hasattr(tool_context, "state") and isinstance(tool_context.state, dict):
            tool_context.state['chart_links'] = chart_to_links

    return {
        "message": f"Your weekly CO2Ops AWS Sustainability report has been generated successfully.",
        "report_url": report_url,
        "charts": chart_to_links
    }

generate_sustainability_report = create_google_doc


def get_forecast_information() -> dict:
    """
    Aggregates forecasted carbon emissions across AWS EC2 instances for the upcoming 7 days.
    """
    date_to_emissions = {}
    instance_to_emissions = {}
    total_emission = 0.0

    for server in DEFAULT_AWS_SERVERS:
        inst_id = server["Instance_ID"]
        fc = generate_aws_forecast(inst_id, metric="carbon", horizon_days=7)
        inst_sum = sum(fc["values"])
        instance_to_emissions[inst_id] = round(inst_sum, 3)
        total_emission += inst_sum

        for d, v in zip(fc["dates"], fc["values"]):
            date_to_emissions[d] = round(date_to_emissions.get(d, 0.0) + v, 3)

    date_with_highest = sorted(date_to_emissions.items(), key=lambda x: x[1], reverse=True)
    top_instances = sorted(instance_to_emissions.items(), key=lambda x: x[1], reverse=True)

    return {
        "Total Carbon Emissions for the week": round(total_emission, 3),
        "Date with Highest Emission": {date_with_highest[0][0]: date_with_highest[0][1]},
        "Top 2 Carbon Emitting instances": [
            {top_instances[0][0]: top_instances[0][1]},
            {top_instances[1][0]: top_instances[1][1]}
        ]
    }

