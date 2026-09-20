# =============================================================================
# CO2Ops - Automated AWS Cloud Deployment Script (Windows PowerShell)
# Builds and deploys the Google ADK Backend and Streamlit Frontend to AWS
# =============================================================================

param(
    [string]$AwsRegion = "us-east-1",
    [string]$BackendRepo = "co2ops-backend",
    [string]$FrontendRepo = "co2ops-frontend"
)

$ErrorActionPreference = "Stop"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " CO2Ops - AWS Cloud Production Deployment" -ForegroundColor Cyan
Write-Host " Targets: Amazon ECR, AWS App Runner / ECS, Amazon S3, SageMaker" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Check AWS CLI Authentication
Write-Host "`n[1/6] Verifying AWS CLI authentication..." -ForegroundColor Yellow
try {
    $CallerIdentity = aws sts get-caller-identity | ConvertFrom-Json
    $AccountId = $CallerIdentity.Account
    Write-Host "Authenticated as Account: $AccountId ($($CallerIdentity.Arn))" -ForegroundColor Green
} catch {
    Write-Host "Error: AWS CLI is not configured or authenticated. Run 'aws configure' first." -ForegroundColor Red
    exit 1
}

$EcrRegistry = "$AccountId.dkr.ecr.$AwsRegion.amazonaws.com"

# 2. Authenticate Docker to Amazon ECR
Write-Host "`n[2/6] Logging in to Amazon ECR ($EcrRegistry)..." -ForegroundColor Yellow
aws ecr get-login-password --region $AwsRegion | docker login --username AWS --password-stdin $EcrRegistry

# 3. Create ECR Repositories if not exist
Write-Host "`n[3/6] Ensuring ECR repositories exist..." -ForegroundColor Yellow
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
Write-Host "`n[4/6] Building & Pushing Backend Container..." -ForegroundColor Yellow
$BackendImageTag = "$EcrRegistry/${BackendRepo}:latest"
docker build -t $BackendRepo -f co2ops_agent/Dockerfile co2ops_agent/
docker tag ${BackendRepo}:latest $BackendImageTag
docker push $BackendImageTag
Write-Host "Backend image pushed successfully: $BackendImageTag" -ForegroundColor Green

# 5. Build and Push Frontend Image (Streamlit Workspace)
Write-Host "`n[5/6] Building & Pushing Frontend Container..." -ForegroundColor Yellow
$FrontendImageTag = "$EcrRegistry/${FrontendRepo}:latest"
docker build -t $FrontendRepo -f Frontend/Dockerfile Frontend/
docker tag ${FrontendRepo}:latest $FrontendImageTag
docker push $FrontendImageTag
Write-Host "Frontend image pushed successfully: $FrontendImageTag" -ForegroundColor Green

# 6. S3 Buckets & Deployment Instructions
Write-Host "`n[6/6] Finalizing AWS Deployment Config..." -ForegroundColor Yellow
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

Write-Host "`n=================================================================" -ForegroundColor Cyan
Write-Host " SUCCESS: Containers Built & Pushed to AWS ECR!" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "To complete the live URL deployment via AWS App Runner:" -ForegroundColor White
Write-Host "  1. Open AWS Console -> App Runner -> Create Service" -ForegroundColor Yellow
Write-Host "  2. Service 1 (Backend):" -ForegroundColor White
Write-Host "     - Image: $BackendImageTag" -ForegroundColor DarkCyan
Write-Host "     - Port: 8080" -ForegroundColor DarkCyan
Write-Host "     - Env: GEMINI_API_KEY=<your_key>, AWS_DEFAULT_REGION=$AwsRegion" -ForegroundColor DarkCyan
Write-Host "  3. Service 2 (Frontend):" -ForegroundColor White
Write-Host "     - Image: $FrontendImageTag" -ForegroundColor DarkCyan
Write-Host "     - Port: 8501" -ForegroundColor DarkCyan
Write-Host "     - Env: CO2OPS_API_URL=<backend_app_runner_url>" -ForegroundColor DarkCyan
Write-Host "=================================================================`n" -ForegroundColor Cyan
