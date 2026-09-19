import os
import pytest
from unittest.mock import patch, MagicMock
from co2ops_agent.secrets_access_manager import access_secret

def test_access_secret_from_env():
    os.environ["TEST_SECRET_KEY"] = "super-secret-value-123"
    try:
        val = access_secret("TEST_SECRET_KEY")
        assert val == "super-secret-value-123"
    finally:
        del os.environ["TEST_SECRET_KEY"]

def test_access_secret_fallback_default():
    val = access_secret("NON_EXISTENT_SECRET_XYZ", default="fallback_default")
    assert val == "fallback_default"

@patch("boto3.client")
def test_access_secret_from_aws_secrets_manager(mock_boto_client):
    mock_sm = MagicMock()
    mock_sm.get_secret_value.return_value = {"SecretString": "aws-sm-secret-val"}
    mock_boto_client.return_value = mock_sm

    val = access_secret("CLIMATIQ_API_KEY_TEST")
    assert val == "aws-sm-secret-val"
    mock_sm.get_secret_value.assert_called_once_with(SecretId="CLIMATIQ_API_KEY_TEST")

@patch("boto3.client")
def test_access_secret_from_aws_ssm(mock_boto_client):
    # Simulate Secrets Manager failing then SSM succeeding
    def client_factory(service_name, **kwargs):
        if service_name == "secretsmanager":
            sm_mock = MagicMock()
            sm_mock.get_secret_value.side_effect = Exception("Not in SM")
            return sm_mock
        elif service_name == "ssm":
            ssm_mock = MagicMock()
            ssm_mock.get_parameter.return_value = {"Parameter": {"Value": "ssm-param-val"}}
            return ssm_mock
        return MagicMock()

    mock_boto_client.side_effect = client_factory

    val = access_secret("SSM_PARAMETER_TEST")
    assert val == "ssm-param-val"
