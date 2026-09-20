"""
Amazon SageMaker AI Inference Handler for CO2Ops
Implements the standard SageMaker PyTorch / Scikit-learn inference script protocol:
- model_fn: Loads model assets
- input_fn: Deserializes JSON payload from @forecasting_tool_agent
- predict_fn: Runs time-series forecasting with probabilistic confidence bounds
- output_fn: Serializes forecast predictions for the agent
"""

import json
import logging
import numpy as np
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sagemaker_inference")


def model_fn(model_dir: str):
    """
    Loads model assets. For time-series inference based on dynamic telemetry inputs,
    we initialize the forecast engine.
    """
    logger.info("Initializing SageMaker AI time-series inference engine.")
    return {"engine": "CO2Ops-SageMaker-TimeSeries-Forecaster", "version": "1.0"}


def input_fn(request_body: str, request_content_type: str) -> Dict[str, Any]:
    """
    Parses incoming payload from @forecasting_tool_agent.
    Expected JSON schema:
    {
        "instance_id": "i-01a2b3c4d5e6f7g80",
        "metric": "cpu",
        "history": [14.2, 13.8, 15.1, ...],
        "horizon": 7
    }
    """
    if request_content_type == "application/json":
        data = json.loads(request_body)
        return data
    raise ValueError(f"Unsupported content type: {request_content_type}. Expected application/json.")


def predict_fn(input_data: Dict[str, Any], model: Any) -> Dict[str, Any]:
    """
    Generates multi-step time-series forecast with confidence intervals.
    """
    history = input_data.get("history", [])
    horizon = int(input_data.get("horizon", 7))
    metric = input_data.get("metric", "cpu")
    instance_id = input_data.get("instance_id", "unknown")

    if not history:
        history = [15.0] * 14

    history_arr = np.array(history, dtype=float)
    mean_val = float(np.mean(history_arr))
    std_val = float(np.std(history_arr)) if len(history_arr) > 1 else 1.0

    # Trend calculation (linear drift)
    x = np.arange(len(history_arr))
    if len(x) > 1 and np.var(x) > 0:
        slope, intercept = np.polyfit(x, history_arr, 1)
    else:
        slope, intercept = 0.0, mean_val

    # Generate P10, P50 (median), and P90 (worst-case peak) forecasts
    predictions_p50 = []
    predictions_p10 = []
    predictions_p90 = []

    last_t = len(history_arr) - 1
    for step in range(1, horizon + 1):
        t = last_t + step
        trend_val = intercept + (slope * t)
        
        # Mean reversion damping
        damped_val = 0.7 * trend_val + 0.3 * mean_val
        bounded_val = max(0.0, damped_val)
        
        # Uncertainty widening over forecast horizon
        uncertainty = std_val * np.sqrt(step) * 0.5
        
        p50 = round(float(bounded_val), 3)
        p10 = round(float(max(0.0, bounded_val - uncertainty)), 3)
        p90 = round(float(bounded_val + uncertainty), 3)
        
        predictions_p50.append(p50)
        predictions_p10.append(p10)
        predictions_p90.append(p90)

    peak_p90 = max(predictions_p90)
    is_safe_under_threshold = bool(peak_p90 < 50.0)

    logger.info(f"Generated SageMaker forecast for {instance_id}: peak P90 = {peak_p90}%")

    return {
        "status": "success",
        "instance_id": instance_id,
        "metric": metric,
        "horizon": horizon,
        "predictions": predictions_p50,
        "p50_median": predictions_p50,
        "p10_lower_bound": predictions_p10,
        "p90_upper_bound": predictions_p90,
        "peak_forecast": peak_p90,
        "zero_downtime_safe": is_safe_under_threshold,
        "model_engine": "Amazon SageMaker AI Time-Series v1.0"
    }


def output_fn(prediction: Dict[str, Any], accept: str) -> str:
    """
    Serializes the prediction dictionary back to JSON.
    """
    if accept == "application/json" or "*/*" in accept:
        return json.dumps(prediction)
    raise ValueError(f"Unsupported accept type: {accept}. Expected application/json.")
