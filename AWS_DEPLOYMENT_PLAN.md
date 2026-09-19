# CO2Ops: AWS Cloud Architecture & Step-by-Step Deployment Guide

This document outlines the blueprint and step-by-step plan for deploying **CO2Ops** onto Amazon Web Services (AWS).

---

## 1. Architecture Overview

```
                      +-----------------------------+
                      |       User Browser          |
                      +--------------+--------------+
                                     |
               +---------------------+---------------------+
               | (HTTPS / CDN)                             | (Direct Console)
               v                                           v
      +------------------+                        +------------------+
      |  Amazon S3 +     |                        | Streamlit /      |
      |  CloudFront      |                        | Web Workspace    |
      | (Landing Page)   |                        | (Port 8501)      |
      +--------+---------+                        +--------+---------+
               |                                           |
               +---------------------+---------------------+
                                     | REST API (/run)
                                     v
                 +---------------------------------------+
                 |       CO2Ops Agent Backend            |
                 | (AWS ECS Fargate / AWS App Runner)    |
                 +---+-------------------------------+---+
                     |                               |
       +-------------+-------------+                 |
       |                           |                 v
       v                           v       +-------------------+
+--------------+           +---------------+|  AWS Secrets      |
| AWS EC2 APIs |           | Climatiq AWS  ||  Manager          |
| (Describe/   |           | Emissions API || (API Credentials) |
|  Modify)     |           +---------------+-------------------+
+--------------+                           |
       |                                   v
       v                           +-------------------+
+--------------+                   |  Amazon S3        |
|  CloudWatch  |                   | (Reports & Slides)|
|  Telemetry   |                   +-------------------+
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

## 8. Step 7: Scheduled Daily Snapshot on AWS Lambda + EventBridge

To replicate continuous telemetry collection and ARIMA training:
1. Deploy `aws_lambda/daily_data_snapshot.py` as an AWS Lambda function.
2. Create an **Amazon EventBridge Rule** with a daily cron schedule:
   ```text
   cron(0 0 * * ? *)
   ```
3. Target: Lambda function `CO2OpsDailySnapshot`.

---

## 9. Verification & Cutover Checklist

- [ ] Verify backend health: `GET https://<app-runner-url>/docs`
- [ ] Verify session creation: `POST /apps/co2ops_agent/users/test/sessions/test-1`
- [ ] Send test prompt via `/run`: *"Audit EC2 instances in us-east-1"*
- [ ] Confirm `@optimization_advisor` returns recommendations
- [ ] Test safe execution workflow with test EC2 instance
- [ ] Confirm executive summary uploaded to S3 bucket `co2ops-sustainability-reports`
