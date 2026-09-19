import pytest
from co2ops_agent.agents.optimization_advisor_agent.sub_agents.infra_scout_agent.agent import (
    get_server_dataframe,
    execute_server_query,
    DEFAULT_AWS_SERVERS
)

def test_get_server_dataframe():
    df = get_server_dataframe()
    assert not df.empty
    assert "Instance_ID" in df.columns
    assert "Instance_Type" in df.columns
    assert "Region" in df.columns
    assert "Average_CPU_Utilization" in df.columns
    assert "Total_Carbon_Emission_in_kg" in df.columns
    assert len(df) >= len(DEFAULT_AWS_SERVERS)

def test_execute_server_query_filter_underutilized():
    sql = "SELECT Instance_ID, Instance_Type, Average_CPU_Utilization FROM server_metrics WHERE Average_CPU_Utilization < 15.0"
    result = execute_server_query(sql)
    assert result["status"] == "success"
    assert result["row_count"] > 0
    for row in result["rows"]:
        assert row["Average_CPU_Utilization"] < 15.0

def test_execute_server_query_aggregation():
    sql = "SELECT Region, COUNT(*) AS count, AVG(Average_CPU_Utilization) AS avg_cpu FROM server_metrics GROUP BY Region ORDER BY count DESC"
    result = execute_server_query(sql)
    assert result["status"] == "success"
    assert len(result["rows"]) > 0
    assert "Region" in result["rows"][0]
    assert "count" in result["rows"][0]

def test_execute_server_query_gcp_syntax_compatibility():
    # Verify legacy GCP backtick syntax is smoothly translated to DuckDB
    sql = "SELECT Instance_ID, Instance_Type FROM `server_metrics` LIMIT 3"
    result = execute_server_query(sql)
    assert result["status"] == "success"
    assert len(result["rows"]) == 3

def test_execute_server_query_syntax_error_handled():
    sql = "SELECT NOT_A_REAL_COLUMN FROM server_metrics"
    result = execute_server_query(sql)
    # Fallback or error status returned safely without raising unhandled exceptions
    assert "status" in result
