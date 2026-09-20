# CO2Ops: AWS Cloud Architecture & Step-by-Step Deployment Guide

This document outlines the blueprint and step-by-step plan for deploying **CO2Ops** onto Amazon Web Services (AWS).

---

## 1. Architecture Overview

```
                      +-----------------------------+
                      |       User Browser          |
                      +--------------+--------------+
                                     | HTTPS (Port 443)
                                     v
                       +----------------------------+
                       |       AWS App Runner       |
                       |    (Live Public HTTPS URL) |
                       +-------------+--------------+
                                     |
               +---------------------+---------------------+
               | Port 8501                                 | Port 8080 (/run)
               v                                           v
      +------------------+                        +------------------+
      | Streamlit App    |----------------------->| Google ADK Agent |
      | Workspace UI     |                        | Multi-Agent Core |
      +------------------+                        +---+----------+---+
                                                      |          |
         +---------------------+----------------------+          v
         |                     |                       +-------------------+
         v                     v                       |  Amazon SageMaker |
  +--------------+      +---------------+              |  AI Endpoint      |
  | AWS EC2 APIs |      | Climatiq AWS  |              |  (DeepAR / ARIMA) |
  | (Describe/   |      | Emissions API |              +-------------------+
  |  Modify)     |      +---------------+                        |
  +-------+------+                                               v
          |                                            +-------------------+
          v                                            |  AWS Secrets      |
  +--------------+                                     |  Manager / SSM    |
  |  CloudWatch  |                                     +-------------------+
  |  Telemetry   |                                               |
  +-------+------+                                               v
          |                                            +-------------------+
          v                                            |  Amazon S3        |
  +--------------+                                     | (Reports & Slides)|
  | AWS Lambda + |                                     +-------------------+
  | EventBridge  |
  +--------------+
```

---

## 2. Step 1: IAM Permissions & Roles

Create an IAM Role `CO2OpsExecutionRole` for the backend service with the following inline or managed policies:

### EC2 & CloudWatch Policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EC2ReadAndModify",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceTypes",
        "ec2:DescribeInstanceStatus",
        "ec2:StopInstances",
        "ec2:StartInstances",
        "ec2:ModifyInstanceAttribute"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchTelemetry",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricData",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics"
      ],
      "Resource": "*"
    },
    {
      "Sid": "PricingApiAccess",
      "Effect": "Allow",
      "Action": [
        "pricing:GetProducts",
        "pricing:DescribeServices",
        "pricing:GetAttributeValues"
      ],
      "Resource": "*"
    }
  ]
}
```

### S3 & Secrets Manager Policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3StorageAccess",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::co2ops-sustainability-reports",
        "arn:aws:s3:::co2ops-sustainability-reports/*"
      ]
    },
    {
      "Sid": "SecretsManagerRead",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:CLIMATIQ_API_KEY*"
    },
    {
      "Sid": "SageMakerInvokeAccess",
      "Effect": "Allow",
      "Action": [
        "sagemaker:InvokeEndpoint"
      ],
      "Resource": "arn:aws:sagemaker:*:*:endpoint/co2ops-*"
    }
  ]
}
```

---

## 3. Step 2: Secrets Configuration in AWS Secrets Manager

Store the Climatiq API key in AWS Secrets Manager:
```bash
aws secretsmanager create-secret \
    --name "CLIMATIQ_API_KEY" \
    --description "Climatiq API Key for CO2Ops carbon calculations" \
    --secret-string "YOUR_CLIMATIQ_KEY" \
    --region us-east-1
```

---

## 4. Step 3: Amazon S3 Bucket Creation

Create the bucket used by `@summary_generator_agent` and `@presentation_generator_agent` to store weekly markdown reports and PowerPoint slides:
```bash
aws s3 mb s3://co2ops-sustainability-reports --region us-east-1
```

---

## 5. Step 4: Containerization & Amazon ECR (Elastic Container Registry)

### 1. Create ECR Repositories:
```bash
aws ecr create-repository --repository-name co2ops-backend --region us-east-1
aws ecr create-repository --repository-name co2ops-frontend --region us-east-1
```

### 2. Authenticate Docker with ECR:
```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
```

### 3. Build and Push Backend Image:
```bash
docker build -t co2ops-backend -f co2ops_agent/Dockerfile .
docker tag co2ops-backend:latest <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/co2ops-backend:latest
docker push <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/co2ops-backend:latest
```

---

## 6. Step 5: Backend Deployment on AWS ECS Fargate or App Runner

### Option A: AWS App Runner (Fastest, Fully Managed Serverless)
1. In AWS Console $\to$ **App Runner** $\to$ **Create Service**.
2. Source: **Container Registry** $\to$ Amazon ECR $\to$ `co2ops-backend:latest`.
3. Service settings:
   - Port: `8080`
   - CPU: `1 vCPU`, Memory: `2 GB`
   - Instance Role: Select `CO2OpsExecutionRole`
   - Environment variables:
     - `AWS_DEFAULT_REGION`: `us-east-1`
     - `GEMINI_API_KEY`: *(Your Gemini API key)*
4. Click **Deploy**. App Runner provides a live HTTPS URL (e.g. `https://xxx.us-east-1.awsapprunner.com`).

### Option B: AWS ECS Fargate
1. Create an ECS Cluster `co2ops-cluster`.
2. Define Task Definition `co2ops-backend-task` (Fargate, 1 vCPU, 2 GB RAM, container port 8080).
3. Create an ECS Service with an Application Load Balancer (ALB) pointing to target group on port 8080.

---

## 7. Step 6: Frontend Deployment

### Option A: Static Landing Page & Web Workspace on Amazon S3 + CloudFront
1. Build static bundle in `Frontend/` (`index.html`, `workspace.html`, `style.css`, `main.js`).
2. Sync files to S3 bucket:
   ```bash
   aws s3 sync Frontend/ s3://co2ops-frontend-web --exclude "app.py" --exclude "*.woff2"
   ```
3. Attach an **Amazon CloudFront Distribution** pointing to the S3 bucket with HTTPS.

### Option B: Streamlit Workspace on ECS / App Runner
1. If using the Streamlit workspace (`Frontend/app.py`):
   ```bash
   docker build -t co2ops-frontend -f Frontend/Dockerfile .
   docker push <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/co2ops-frontend:latest
   ```
2. Deploy container to App Runner on port `8501`.

---

## 8. Step 7: Amazon SageMaker AI Serverless Endpoint (Predictive Forecaster)

Deploy the serverless time-series forecasting endpoint:
```bash
python co2ops_agent/sagemaker_model/deploy_endpoint.py
```
This deploys `co2ops-load-forecaster` as an AWS SageMaker Serverless Endpoint. Add the endpoint name to your environment:
```bash
export SAGEMAKER_ENDPOINT_NAME=co2ops-load-forecaster
export SAGEMAKER_REGION=us-east-1
```

---

## 9. Step 8: Scheduled Daily Snapshot on AWS Lambda + EventBridge

To replicate continuous telemetry collection:
1. Deploy `aws_lambda/daily_data_snapshot.py` as an AWS Lambda function.
2. Create an **Amazon EventBridge Rule** with a daily cron schedule:
   ```text
   cron(0 0 * * ? *)
   ```
3. Target: Lambda function `CO2OpsDailySnapshot`.

---

## 10. Automated One-Command Deployment

We provide automated deployment scripts that build and push both containers to Amazon ECR and configure S3:

- **Windows (PowerShell)**:
  ```powershell
  .\deploy_aws.ps1 -AwsRegion us-east-1
  ```
- **Linux / macOS (Bash)**:
  ```bash
  chmod +x deploy_aws.sh
  ./deploy_aws.sh us-east-1
  ```

---

## 11. Verification & Cutover Checklist

- [ ] Verify backend health: `GET https://<app-runner-url>/`
- [ ] Verify Streamlit frontend: open `https://<frontend-app-runner-url>`
- [ ] Verify session creation: `POST /apps/co2ops_agent/users/test/sessions/test-1`
- [ ] Send test prompt: *"Audit EC2 instances in us-east-1"*
- [ ] Confirm `@forecasting_tool_agent` queries SageMaker (or local fallback)
- [ ] Confirm `@optimization_advisor` returns recommendations
- [ ] Test safe execution workflow with test EC2 instance
- [ ] Confirm executive summary uploaded to S3 bucket `co2ops-sustainability-reports`
- [ ] Test safe execution workflow with test EC2 instance
- [ ] Confirm executive summary uploaded to S3 bucket `co2ops-sustainability-reports`
