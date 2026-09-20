#!/usr/bin/env python3
"""
CO2Ops - Amazon SageMaker AI Serverless Endpoint Deployment Script
Packages inference.py into a SageMaker model and deploys a Serverless Inference Endpoint.
Serverless endpoints scale to 0 instances when idle, incurring zero cost between queries.
"""

import os
import sys
import tarfile
import tempfile
import time
import boto3

REGION = os.getenv("SAGEMAKER_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
ENDPOINT_NAME = os.getenv("SAGEMAKER_ENDPOINT_NAME", "co2ops-load-forecaster")
ROLE_ARN = os.getenv("SAGEMAKER_EXECUTION_ROLE_ARN")
BUCKET_NAME = os.getenv("AWS_METRICS_BUCKET", "co2ops-sagemaker-artifacts")

import json

def get_or_create_sagemaker_role(region: str) -> str:
    """Detects or creates an IAM execution role for SageMaker."""
    if ROLE_ARN:
        return ROLE_ARN
    
    iam = boto3.client("iam", region_name=region)
    role_name = "CO2OpsSageMakerExecutionRole"
    try:
        role = iam.get_role(RoleName=role_name)
        print(f"Found existing SageMaker role: {role['Role']['Arn']}")
        return role["Role"]["Arn"]
    except Exception:
        print(f"Creating IAM role '{role_name}' for SageMaker...")
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "sagemaker.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        try:
            role = iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Execution role for CO2Ops SageMaker serverless inference"
            )
            iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
            )
            time.sleep(8)  # Wait for IAM role propagation across AWS
            return role["Role"]["Arn"]
        except Exception as err:
            print(f"IAM role notice: {err}")
            sts = boto3.client("sts")
            account_id = sts.get_caller_identity()["Account"]
            return f"arn:aws:iam::{account_id}:role/service-role/AmazonSageMaker-ExecutionRole"

def package_code(tar_path: str):
    """Tarballs inference.py for SageMaker."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    inference_path = os.path.join(script_dir, "inference.py")
    
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(inference_path, arcname="code/inference.py")
    print(f"Packaged {inference_path} -> {tar_path}")

def deploy():
    print("=" * 65)
    print("CO2Ops - Deploying Amazon SageMaker AI Serverless Endpoint")
    print(f"Region: {REGION} | Target Endpoint: {ENDPOINT_NAME}")
    print("=" * 65)

    execution_role_arn = get_or_create_sagemaker_role(REGION)
    print(f"Using Execution Role: {execution_role_arn}")

    s3 = boto3.client("s3", region_name=REGION)
    sm = boto3.client("sagemaker", region_name=REGION)

    # 1. Ensure S3 bucket exists
    try:
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=BUCKET_NAME)
        else:
            s3.create_bucket(
                Bucket=BUCKET_NAME,
                CreateBucketConfiguration={"LocationConstraint": REGION}
            )
        print(f"Created/Verified S3 artifact bucket: s3://{BUCKET_NAME}")
    except Exception as e:
        print(f"Bucket notice: {e}")

    # 2. Upload code tarball
    with tempfile.TemporaryDirectory() as tmpdir:
        tar_path = os.path.join(tmpdir, "model.tar.gz")
        package_code(tar_path)
        s3_key = f"models/{ENDPOINT_NAME}/model.tar.gz"
        s3.upload_file(tar_path, BUCKET_NAME, s3_key)
        model_data_url = f"s3://{BUCKET_NAME}/{s3_key}"
        print(f"Uploaded model artifacts to {model_data_url}")

    # 3. Create SageMaker Model
    model_name = f"{ENDPOINT_NAME}-model-{int(time.time())}"
    image_uri = f"683313688378.dkr.ecr.{REGION}.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3"

    print(f"Creating SageMaker Model: {model_name}...")
    sm.create_model(
        ModelName=model_name,
        PrimaryContainer={
            "Image": image_uri,
            "ModelDataUrl": model_data_url,
            "Environment": {
                "SAGEMAKER_PROGRAM": "code/inference.py",
                "SAGEMAKER_SUBMIT_DIRECTORY": model_data_url
            }
        },
        ExecutionRoleArn=execution_role_arn
    )

    # 4. Create Serverless Endpoint Configuration
    config_name = f"{ENDPOINT_NAME}-config-{int(time.time())}"
    print(f"Creating Serverless Endpoint Config: {config_name} (Memory: 1024MB, Max Concurrency: 5)...")
    sm.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[
            {
                "VariantName": "AllTraffic",
                "ModelName": model_name,
                "ServerlessConfig": {
                    "MemorySizeInMB": 1024,
                    "MaxConcurrency": 5
                }
            }
        ]
    )

    # 5. Create or Update Endpoint
    try:
        sm.describe_endpoint(EndpointName=ENDPOINT_NAME)
        print(f"Updating existing endpoint {ENDPOINT_NAME}...")
        sm.update_endpoint(
            EndpointName=ENDPOINT_NAME,
            EndpointConfigName=config_name
        )
    except sm.exceptions.ClientError:
        print(f"Creating new SageMaker serverless endpoint {ENDPOINT_NAME}...")
        sm.create_endpoint(
            EndpointName=ENDPOINT_NAME,
            EndpointConfigName=config_name
        )

    print("\nSageMaker Serverless Endpoint creation initiated successfully!")
    print(f"Add the following to your .env:\n  SAGEMAKER_ENDPOINT_NAME={ENDPOINT_NAME}\n  SAGEMAKER_REGION={REGION}")

if __name__ == "__main__":
    deploy()
