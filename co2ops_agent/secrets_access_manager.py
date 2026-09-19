import os
import logging

logger = logging.getLogger(__name__)

def access_secret(secret_id: str, default: str = "") -> str:
    """
    Retrieves a secret from environment variables first, then attempts
    AWS Secrets Manager or AWS SSM Parameter Store.
    Returns `default` if not found.
    """
    # 1. Check direct environment variable
    val = os.getenv(secret_id)
    if val:
        return val

    # 2. Attempt AWS Secrets Manager
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError

        region = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION", "us-east-1"))
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_id)
        if "SecretString" in response:
            return response["SecretString"]
    except Exception as e:
        logger.debug(f"Could not load secret '{secret_id}' from AWS Secrets Manager: {e}")

    # 3. Attempt AWS SSM Parameter Store
    try:
        import boto3
        region = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION", "us-east-1"))
        ssm = boto3.client("ssm", region_name=region)
        param = ssm.get_parameter(Name=secret_id, WithDecryption=True)
        return param["Parameter"]["Value"]
    except Exception as e:
        logger.debug(f"Could not load parameter '{secret_id}' from AWS SSM: {e}")

    return default