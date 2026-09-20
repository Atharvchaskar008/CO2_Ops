# Step-by-Step Guide: Deploying CO2Ops to AWS

This guide walks you through deploying **CO2Ops** to AWS to get your live **HTTPS URL** and fulfill the **"SHIP IT"** hackathon rubric requirements using **Amazon ECR**, **AWS App Runner**, **Amazon SageMaker AI**, and **Amazon S3**.

---

## Prerequisites (5 Minutes)

Before starting, ensure you have:
1. **An AWS Account** (Free tier / $200 credits).
2. **AWS CLI installed & configured**:
   - Verify by running in terminal:
     ```bash
     aws sts get-caller-identity
     ```
   - If not configured, run `aws configure` and enter your AWS Access Key, Secret Key, and default region (e.g., `us-east-1`).
3. **Docker Desktop installed and running** on your machine.
4. **Your Gemini API Key**:
   - Get one from [Google AI Studio](https://aistudio.google.com/app/apikey).

---

## Step 1: Build & Push Containers to Amazon ECR

We provide an automated script that logs into Amazon ECR, creates the repositories, builds both containers, and pushes them. It also has a flag to deploy the **Amazon SageMaker AI Serverless Endpoint** automatically!

### On Windows (PowerShell):
Open PowerShell in the `d:\Projects\CO2Ops` directory:

**Option A (Recommended - Full Stack + SageMaker AI)**:
```powershell
.\deploy_aws.ps1 -AwsRegion us-east-1 -DeploySageMaker
```

**Option B (Containers Only - Local ARIMA Fallback)**:
```powershell
.\deploy_aws.ps1 -AwsRegion us-east-1
```

### On macOS / Linux (Bash):
```bash
chmod +x deploy_aws.sh
# With SageMaker:
./deploy_aws.sh us-east-1 --with-sagemaker

# Or containers only:
./deploy_aws.sh us-east-1
```

### What this step does:
- Authenticates Docker with your account's Amazon ECR registry: `<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com`.
- Builds `co2ops-backend` (Google ADK agent engine on port 8080).
- Builds `co2ops-frontend` (Streamlit workspace on port 8501).
- Pushes both images to your private ECR repositories.
- Creates an S3 bucket: `s3://co2ops-sustainability-<ACCOUNT_ID>`.
- *(If `-DeploySageMaker` is passed)*: Packages `co2ops_agent/sagemaker_model/inference.py` and deploys the `co2ops-load-forecaster` serverless endpoint on AWS SageMaker!

---

## Step 2: Deploy the Backend on AWS App Runner (Port 8080)

AWS App Runner provides a managed, serverless container runner with an automatic public **HTTPS URL**.

1. Open the [AWS Management Console](https://console.aws.amazon.com/) and search for **App Runner**.
2. Click **Create service**.
3. **Source and deployment**:
   - Repository type: **Container registry**.
   - Provider: **Amazon ECR**.
   - Container image URI: Click **Browse** and select `co2ops-backend:latest`.
   - Deployment trigger: **Manual** (or Automatic).
   - ECR access role: Choose **Create new service role** (or select existing `AppRunnerECRAccessRole`).
   - Click **Next**.
4. **Configure service**:
   - Service name: `co2ops-backend`
   - Virtual CPU (vCPU): **1 vCPU**
   - Memory: **2 GB**
   - Port: `8080`
   - **Environment variables**: Add the following:
     | Key | Value |
     | :--- | :--- |
     | `GEMINI_API_KEY` | *(Paste your Gemini API key)* |
     | `GEMINI_MODEL` | `gemini-2.5-flash` |
     | `AWS_DEFAULT_REGION` | `us-east-1` |
     | `AWS_METRICS_BUCKET` | `co2ops-sustainability-<ACCOUNT_ID>` |
   - **Security**:
     - Instance role: Select or create an IAM role with `CloudWatchReadOnlyAccess` and `AmazonEC2ReadOnlyAccess`.
5. Click **Next**, review the configuration, and click **Create & deploy**.
6. Wait 3–4 minutes until the status turns **Running**.
7. **Copy your Default domain URL**:
   - Example: `https://abcd1234ef.us-east-1.awsapprunner.com`
   - *(Keep this URL handy for Step 3!)*

---

## Step 3: Deploy the Streamlit Frontend on AWS App Runner (Port 8501)

Now deploy the frontend container and connect it to your backend App Runner URL.

1. In the AWS App Runner console, click **Create service**.
2. **Source and deployment**:
   - Repository type: **Container registry**.
   - Provider: **Amazon ECR**.
   - Container image URI: Click **Browse** and select `co2ops-frontend:latest`.
   - Deployment trigger: **Manual**.
   - ECR access role: Select the same `AppRunnerECRAccessRole`.
   - Click **Next**.
3. **Configure service**:
   - Service name: `co2ops-frontend`
   - Virtual CPU: **1 vCPU**
   - Memory: **2 GB**
   - Port: `8501`
   - **Environment variables**: Add:
     | Key | Value |
     | :--- | :--- |
     | `CO2OPS_API_URL` | *(Paste the backend URL from Step 2, e.g. `https://abcd1234ef.us-east-1.awsapprunner.com`)* |
4. Click **Next**, review, and click **Create & deploy**.
5. Wait 3–4 minutes until the status turns **Running**.
6. **Congratulations! Your live frontend URL is ready**:
   - Example: `https://xyz9876wvu.us-east-1.awsapprunner.com`
   - Open this URL in your browser to interact with the live **CO2Ops Streamlit Console**.

---

## Step 4 (Optional): Deploy SageMaker Serverless Endpoint

To activate the **Amazon SageMaker AI** predictive inference endpoint for `@forecasting_tool_agent`:

1. Run the included deployment script:
   ```bash
   python co2ops_agent/sagemaker_model/deploy_endpoint.py
   ```
2. This creates an AWS SageMaker Serverless Endpoint named:
   `co2ops-load-forecaster`
3. Add `SAGEMAKER_ENDPOINT_NAME=co2ops-load-forecaster` to your `co2ops-backend` App Runner environment variables.
   *(Note: If you skip this step, CO2Ops automatically falls back to its built-in local ARIMA model, so the system works 100% either way!)*

---

## Step 5: Test & Verify Your Live Deployment

1. Open your live frontend App Runner URL in any browser.
2. In the sidebar:
   - Click **"➕ Create Session"**.
3. In the chat input, test an audit query:
   > *"Find underutilized EC2 instances in us-east-1 and calculate carbon reduction"*
4. Verify that:
   - The Google ADK agents coordinate across the fleet.
   - Predictions and rightsizing comparisons return cleanly in the chat.
   - The session ID persists across messages.

---

## Submitting to the Hackathon

When submitting for the **"SHIP IT: Deployed, with a URL"** track:
- **Live Demo URL**: Paste your Frontend App Runner URL (`https://<frontend-id>.us-east-1.awsapprunner.com`).
- **AWS Services Highlight**:
  - **Compute & Hosting**: AWS App Runner (Containers for ADK backend & Streamlit UI).
  - **AI & MLOps**: Amazon SageMaker AI (`co2ops-load-forecaster` serverless endpoint) + Google ADK with Gemini.
  - **Observability & Data**: Amazon CloudWatch (telemetry metrics) & Amazon S3 (reports & data snapshots).
  - **Automation**: AWS Lambda + EventBridge cron (daily metrics snapshot).

---

## Summary of Useful Commands

| Action | Command |
| :--- | :--- |
| Build & push containers | `.\deploy_aws.ps1 -AwsRegion us-east-1` |
| Run local test suite | `.\.venv\Scripts\pytest.exe -v` |
| Test local full stack | `.\run_local.ps1` |
| Deploy SageMaker endpoint | `python co2ops_agent/sagemaker_model/deploy_endpoint.py` |
