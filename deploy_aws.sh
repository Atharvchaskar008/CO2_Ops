#!/usr/bin/env bash
# =============================================================================
# CO2Ops - Automated AWS Cloud Deployment Script (Bash)
# =============================================================================
set -e

AWS_REGION="${1:-us-east-1}"
BACKEND_REPO="co2ops-backend"
FRONTEND_REPO="co2ops-frontend"

echo "================================================================="
echo " CO2Ops - AWS Cloud Production Deployment"
echo " Region: $AWS_REGION"
echo "================================================================="

# 1. Verify AWS Authentication
echo "[1/5] Verifying AWS CLI authentication..."
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
echo "Authenticated as Account: $ACCOUNT_ID"

ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# 2. Login to ECR
echo "[2/5] Logging in to Amazon ECR..."
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

# 3. Create Repositories
echo "[3/5] Ensuring ECR repositories exist..."
aws ecr describe-repositories --repository-names "$BACKEND_REPO" --region "$AWS_REGION" >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name "$BACKEND_REPO" --region "$AWS_REGION"

aws ecr describe-repositories --repository-names "$FRONTEND_REPO" --region "$AWS_REGION" >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name "$FRONTEND_REPO" --region "$AWS_REGION"

# 4. Build & Push Backend
echo "[4/5] Building and pushing Backend..."
BACKEND_IMAGE="${ECR_REGISTRY}/${BACKEND_REPO}:latest"
docker build -t "$BACKEND_REPO" -f co2ops_agent/Dockerfile co2ops_agent/
docker tag "${BACKEND_REPO}:latest" "$BACKEND_IMAGE"
docker push "$BACKEND_IMAGE"

# 5. Build & Push Frontend
echo "[5/5] Building and pushing Frontend..."
FRONTEND_IMAGE="${ECR_REGISTRY}/${FRONTEND_REPO}:latest"
docker build -t "$FRONTEND_REPO" -f Frontend/Dockerfile Frontend/
docker tag "${FRONTEND_REPO}:latest" "$FRONTEND_IMAGE"
docker push "$FRONTEND_IMAGE"

echo "================================================================="
echo " SUCCESS! Images are ready in Amazon ECR:"
echo " Backend:  $BACKEND_IMAGE (Port 8080)"
echo " Frontend: $FRONTEND_IMAGE (Port 8501)"
echo "================================================================="
