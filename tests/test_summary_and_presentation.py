import os
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from co2ops_agent.agents.summary_generator_agent.tools.tools import (
    generate_weekly_timeseries_df,
    get_weekly_data,
    build_charts,
    get_forecast_information,
    run_query,
    upload_to_s3_or_local
)
from co2ops_agent.agents.presentation_generator_agent.presentation_file_creator import (
    upload_pptx_to_s3_or_local
)

def test_generate_weekly_timeseries_df():
    df = generate_weekly_timeseries_df()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "date" in df.columns
    assert "instance_id" in df.columns
    assert "cpu_util" in df.columns
    assert "memory_util" in df.columns
    assert "total_carbon" in df.columns
    # 7 days * 10 servers = 70 records
    assert len(df) == 70

def test_get_weekly_data():
    data = get_weekly_data()
    assert isinstance(data, list)
    assert len(data) == 10
    first = data[0]
    assert "instance_id" in first
    assert "average_cpu_utilization" in first
    assert "average_memory_utilization" in first
    assert "total_carbon_emission_kg" in first

def test_run_query_duckdb():
    sql = "SELECT region, AVG(cpu_util) as avg_cpu FROM server_metrics_timeseries GROUP BY region"
    df = run_query(sql)
    assert not df.empty
    assert "region" in df.columns
    assert "avg_cpu" in df.columns

def test_build_charts():
    charts = build_charts()
    assert "carbon_timeseries" in charts
    assert "region_utilization" in charts
    assert "cpu_vs_carbon" in charts
    assert "underutilization" in charts
    for name, path in charts.items():
        assert os.path.exists(path), f"Chart {name} was not created at {path}"

def test_get_forecast_information():
    info = get_forecast_information()
    assert "Total Carbon Emissions for the week" in info
    assert "Date with Highest Emission" in info
    assert "Top 2 Carbon Emitting instances" in info
    assert info["Total Carbon Emissions for the week"] > 0

def test_upload_to_s3_or_local_fallback():
    with patch.dict(os.environ, {"AWS_REPORTS_BUCKET": ""}):
        link = upload_to_s3_or_local("README.md")
        assert link.startswith("file:///")

def test_upload_pptx_to_s3_or_local_fallback():
    with patch.dict(os.environ, {"AWS_REPORTS_BUCKET": ""}):
        link = upload_pptx_to_s3_or_local("sample.pptx", "sample.pptx")
        assert link.startswith("file:///")

@patch("boto3.client")
def test_upload_to_s3_mocked(mock_boto):
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/test-bucket/charts/chart1.png?presigned"
    mock_boto.return_value = mock_s3

    with patch.dict(os.environ, {"AWS_REPORTS_BUCKET": "test-s3-bucket"}):
        link = upload_to_s3_or_local("README.md")
        assert "presigned" in link
        mock_s3.upload_file.assert_called_once()
