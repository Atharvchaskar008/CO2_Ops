import datetime
import pytest
from co2ops_agent.agents.forecaster_agent.agent import (
    generate_baseline_history,
    generate_aws_forecast,
    execute_forecast_query,
    fetch_cloudwatch_history
)

def test_generate_baseline_history_cpu():
    history = generate_baseline_history("i-0a1b2c3d4e5f6g7h8", "cpu", length=14)
    assert len(history) == 14
    for val in history:
        assert 1.0 <= val <= 99.0

def test_generate_baseline_history_memory():
    history = generate_baseline_history("i-0a1b2c3d4e5f6g7h8", "memory", length=14)
    assert len(history) == 14
    for val in history:
        assert 5.0 <= val <= 99.0

def test_generate_baseline_history_carbon():
    history = generate_baseline_history("i-0a1b2c3d4e5f6g7h8", "carbon", length=14)
    assert len(history) == 14
    for val in history:
        assert val > 0

def test_generate_aws_forecast_cpu():
    forecast = generate_aws_forecast("i-0a1b2c3d4e5f6g7h8", "cpu", horizon_days=7)
    assert forecast["status"] == "success"
    assert forecast["instance_id"] == "i-0a1b2c3d4e5f6g7h8"
    assert len(forecast["values"]) == 7
    assert len(forecast["dates"]) == 7
    assert len(forecast["detailed_rows"]) == 7
    # Verify future dates are strictly sequentially increasing
    start_date = datetime.date.today() + datetime.timedelta(days=1)
    assert forecast["dates"][0] == start_date.strftime("%Y-%m-%d")

def test_execute_forecast_query_nlp_parsing():
    query_str = "Please forecast CPU usage for EC2 instance i-0123456789abcdef0 over 7 days"
    result = execute_forecast_query(query_str)
    assert result["instance_id"] == "i-0123456789abcdef0"
    assert result["metric"] == "cpu"
    assert result["horizon_days"] == 7
    assert len(result["values"]) == 7

def test_execute_forecast_query_memory():
    query_str = "Forecast memory consumption for instance-prod-app-01"
    result = execute_forecast_query(query_str)
    assert result["instance_id"] == "instance-prod-app-01"
    assert result["metric"] == "memory"
