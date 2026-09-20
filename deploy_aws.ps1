# =============================================================================
# CO2Ops - Automated AWS Cloud Deployment Script (Windows PowerShell)
# Builds and deploys the Google ADK Backend and Streamlit Frontend to AWS
# =============================================================================

param(
    [string]$AwsRegion = "us-east-1",
    [string]$BackendRepo = "co2ops-backend",
    [string]$FrontendRepo = "co2ops-frontend",
    [switch]$DeploySageMaker = $false
)

$ErrorActionPreference = "Stop"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " CO2Ops - AWS Cloud Production Deployment" -ForegroundColor Cyan
Write-Host " Targets: Amazon ECR, AWS App Runner / ECS, Amazon S3, SageMaker" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# Auto-detect AWS CLI if not in current session PATH
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    $AwsLocations = @(
        "$env:LOCALAPPDATA\Programs\Amazon\AWSCLIV2",
        "C:\Program Files\Amazon\AWSCLIV2"
    )
    foreach ($loc in $AwsLocations) {
        if (Test-Path "$loc\aws.exe") {
            $env:Path = "$loc;$env:Path"
            break
        }
    }
}

# Auto-detect Docker CLI if not in current session PATH
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    $DockerLocations = @(
        "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin",
        "C:\Program Files\Docker\Docker\resources\bin"
    )
    foreach ($loc in $DockerLocations) {
        if (Test-Path "$loc\docker.exe") {
            $env:Path = "$loc;$env:Path"
            break
        }
    }
}

# 1. Check AWS CLI Authentication
Write-Host "`n[1/7] Verifying AWS CLI authentication..." -ForegroundColor Yellow
$CallerIdentity = $null
try {
    $IdentityOutput = aws sts get-caller-identity 2>&1
    if ($LASTEXITCODE -eq 0) {
        $CallerIdentity = $IdentityOutput | Out-String | ConvertFrom-Json
    }
} catch {
    $CallerIdentity = $null
}

if (-not $CallerIdentity -or -not $CallerIdentity.Account) {
    Write-Host "Error: AWS CLI is not configured or authenticated." -ForegroundColor Red
    Write-Host "Please run 'aws configure' and enter your AWS Access Key ID, Secret Access Key, and default region (e.g., us-east-1)." -ForegroundColor Yellow
    exit 1
}

$AccountId = $CallerIdentity.Account
Write-Host "Authenticated as Account: $AccountId ($($CallerIdentity.Arn))" -ForegroundColor Green

# Verify Docker is running
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "`nError: 'docker' command not found. Please ensure Docker Desktop is installed." -ForegroundColor Red
    exit 1
}

Write-Host "Verifying Docker engine..." -ForegroundColor DarkGray
& docker info >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nError: Docker engine is not running. Please open Docker Desktop and wait until the engine starts." -ForegroundColor Red
    exit 1
}

$EcrRegistry = "$AccountId.dkr.ecr.$AwsRegion.amazonaws.com"

# 2. Authenticate Docker to Amazon ECR
Write-Host "`n[2/7] Logging in to Amazon ECR ($EcrRegistry)..." -ForegroundColor Yellow
aws ecr get-login-password --region $AwsRegion | docker login --username AWS --password-stdin $EcrRegistry

# 3. Create ECR Repositories if not exist
Write-Host "`n[3/7] Ensuring ECR repositories exist..." -ForegroundColor Yellow
foreach ($repo in @($BackendRepo, $FrontendRepo)) {
    try {
        aws ecr describe-repositories --repository-names $repo --region $AwsRegion | Out-Null
        Write-Host "Repository '$repo' exists." -ForegroundColor DarkGray
    } catch {
        Write-Host "Creating repository '$repo'..." -ForegroundColor Cyan
        aws ecr create-repository --repository-name $repo --region $AwsRegion | Out-Null
    }
}

# 4. Build and Push Backend Image (Google ADK Agent Engine)
Write-Host "`n[4/7] Building & Pushing Backend Container..." -ForegroundColor Yellow
$BackendImageTag = "$EcrRegistry/${BackendRepo}:latest"
docker build -t $BackendRepo -f co2ops_agent/Dockerfile co2ops_agent/
docker tag ${BackendRepo}:latest $BackendImageTag
docker push $BackendImageTag
Write-Host "Backend image pushed successfully: $BackendImageTag" -ForegroundColor Green

# 5. Build and Push Frontend Image (Streamlit Workspace)
Write-Host "`n[5/7] Building & Pushing Frontend Container..." -ForegroundColor Yellow
$FrontendImageTag = "$EcrRegistry/${FrontendRepo}:latest"
docker build -t $FrontendRepo -f Frontend/Dockerfile Frontend/
docker tag ${FrontendRepo}:latest $FrontendImageTag
docker push $FrontendImageTag
Write-Host "Frontend image pushed successfully: $FrontendImageTag" -ForegroundColor Green

# 6. S3 Buckets & Deployment Config
Write-Host "`n[6/7] Finalizing S3 Storage Buckets..." -ForegroundColor Yellow
$BucketName = "co2ops-sustainability-$AccountId"
try {
    if ($AwsRegion -eq "us-east-1") {
        aws s3 mb "s3://$BucketName" | Out-Null
    } else {
        aws s3 mb "s3://$BucketName" --region $AwsRegion | Out-Null
    }
    Write-Host "S3 bucket ready: s3://$BucketName" -ForegroundColor Green
} catch {
    Write-Host "Bucket notice: $_" -ForegroundColor DarkGray
}

# 7. (Optional) Deploy Amazon SageMaker AI Serverless Endpoint
if ($DeploySageMaker) {
    Write-Host "`n[7/7] Deploying Amazon SageMaker AI Serverless Endpoint..." -ForegroundColor Yellow
    $env:SAGEMAKER_REGION = $AwsRegion
    $env:SAGEMAKER_ENDPOINT_NAME = "co2ops-load-forecaster"
    $env:AWS_METRICS_BUCKET = $BucketName
    $PythonExe = if (Test-Path (Join-Path $PSScriptRoot ".venv\Scripts\python.exe")) {
        Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    } else {
        "python"
    }
    & $PythonExe (Join-Path $PSScriptRoot "co2ops_agent\sagemaker_model\deploy_endpoint.py")
} else {
    Write-Host "`n[7/7] SageMaker deployment skipped. (Pass -DeploySageMaker to deploy serverless ML endpoint)" -ForegroundColor DarkGray
}

Write-Host "`n=================================================================" -ForegroundColor Cyan
Write-Host " SUCCESS: Containers Built & Pushed to AWS ECR!" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "To complete the live URL deployment via AWS App Runner:" -ForegroundColor White
Write-Host "  1. Open AWS Console -> App Runner -> Create Service" -ForegroundColor Yellow
Write-Host "  2. Service 1 (Backend):" -ForegroundColor White
Write-Host "     - Image: $BackendImageTag" -ForegroundColor DarkCyan
Write-Host "     - Port: 8080" -ForegroundColor DarkCyan
Write-Host "     - Environment Variables:" -ForegroundColor DarkCyan
Write-Host "         GEMINI_API_KEY=<your_gemini_key>" -ForegroundColor White
Write-Host "         AWS_DEFAULT_REGION=$AwsRegion" -ForegroundColor White
Write-Host "         SAGEMAKER_ENDPOINT_NAME=co2ops-load-forecaster  (optional)" -ForegroundColor White
Write-Host "         SAGEMAKER_REGION=$AwsRegion                     (optional)" -ForegroundColor White
Write-Host "  3. Service 2 (Frontend):" -ForegroundColor White
Write-Host "     - Image: $FrontendImageTag" -ForegroundColor DarkCyan
Write-Host "     - Port: 8501" -ForegroundColor DarkCyan
Write-Host "     - Environment Variables:" -ForegroundColor DarkCyan
Write-Host "         CO2OPS_API_URL=<backend_app_runner_url>" -ForegroundColor White
Write-Host "=================================================================`n" -ForegroundColor Cyan
