import json
import os
import unittest
from unittest.mock import patch, MagicMock
import io
import pytest

from co2ops_agent.agents.forecaster_agent.agent import (
    invoke_sagemaker_forecast,
    generate_aws_forecast,
    execute_forecast_query
)
from co2ops_agent.sagemaker_model import inference


class TestSageMakerForecaster(unittest.TestCase):

    def test_sagemaker_invocation_success(self):
        """Test that generate_aws_forecast calls SageMaker endpoint when SAGEMAKER_ENDPOINT_NAME is set."""
        mock_predictions = [16.2, 15.9, 17.1, 18.0, 16.5, 15.8, 17.4]
        mock_response_body = json.dumps({"predictions": mock_predictions}).encode("utf-8")

        mock_sagemaker_client = MagicMock()
        mock_sagemaker_client.invoke_endpoint.return_value = {
            "Body": io.BytesIO(mock_response_body)
        }

        with patch.dict(os.environ, {"SAGEMAKER_ENDPOINT_NAME": "test-co2ops-endpoint"}):
            with patch("boto3.client", return_value=mock_sagemaker_client):
                result = generate_aws_forecast("i-01a2b3c4d5e6f7g80", "cpu", horizon_days=7)

                self.assertEqual(result["status"], "success")
                self.assertEqual(result["engine"], "Amazon SageMaker AI")
                self.assertEqual(result["values"], mock_predictions)
                self.assertEqual(len(result["detailed_rows"]), 7)
                mock_sagemaker_client.invoke_endpoint.assert_called_once()

    def test_sagemaker_fallback_when_unset(self):
        """Test that generate_aws_forecast uses Local ARIMA when SAGEMAKER_ENDPOINT_NAME is unset."""
        with patch.dict(os.environ, {}, clear=True):
            if "SAGEMAKER_ENDPOINT_NAME" in os.environ:
                del os.environ["SAGEMAKER_ENDPOINT_NAME"]

            result = generate_aws_forecast("i-01a2b3c4d5e6f7g80", "cpu", horizon_days=7)

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["engine"], "Local ARIMA")
            self.assertEqual(len(result["values"]), 7)

    def test_sagemaker_error_fallback(self):
        """Test that an error in SageMaker invocation triggers graceful fallback to Local ARIMA."""
        mock_sagemaker_client = MagicMock()
        mock_sagemaker_client.invoke_endpoint.side_effect = RuntimeError("Endpoint not found or unreachable")

        with patch.dict(os.environ, {"SAGEMAKER_ENDPOINT_NAME": "test-failing-endpoint"}):
            with patch("boto3.client", return_value=mock_sagemaker_client):
                result = generate_aws_forecast("i-01a2b3c4d5e6f7g80", "cpu", horizon_days=7)

                self.assertEqual(result["status"], "success")
                self.assertEqual(result["engine"], "Local ARIMA")
                self.assertEqual(len(result["values"]), 7)

    def test_sagemaker_inference_handler_functions(self):
        """Direct unit test of the SageMaker inference script functions."""
        model = inference.model_fn("/tmp/model")
        self.assertIn("engine", model)

        raw_json = json.dumps({
            "instance_id": "i-test12345",
            "metric": "cpu",
            "history": [10.0, 11.5, 12.0, 11.8, 12.5, 13.0, 12.8, 13.2, 12.9, 13.5, 13.1, 13.8, 13.6, 14.0],
            "horizon": 7
        })

        input_data = inference.input_fn(raw_json, "application/json")
        self.assertEqual(input_data["instance_id"], "i-test12345")

        predictions = inference.predict_fn(input_data, model)
        self.assertEqual(predictions["status"], "success")
        self.assertEqual(len(predictions["predictions"]), 7)
        self.assertIn("p90_upper_bound", predictions)
        self.assertIn("zero_downtime_safe", predictions)

        output_str = inference.output_fn(predictions, "application/json")
        parsed_output = json.loads(output_str)
        self.assertEqual(parsed_output["instance_id"], "i-test12345")
