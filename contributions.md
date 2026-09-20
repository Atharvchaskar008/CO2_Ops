# Contributing to CO2Ops 🌱

Welcome to the **CO2Ops** open-source project! We are building an autonomous, mathematical-safety-guaranteed cloud sustainability and FinOps engine for Amazon Web Services (AWS). CO2Ops continuously audits, forecasts, and rightsizes AWS compute infrastructure to eliminate cloud waste and slash carbon emissions.

Whether you're an AWS cloud architect, AI engineer, FinOps specialist, or frontend developer, we welcome your contributions!

---

## 📊 Current Project Status & Roadmap

The following status matrix outlines the current verification state of each architectural component across CO2Ops. **Use this table as your guide for where contributions are most urgently needed:**

| Area | Current Status | Description & Verification State | Priority for Contributors |
|---|:---:|---|:---:|
| **Backend Python Code** | ✅ Working | Core multi-agent framework, DuckDB analytics, and state management are operational. | Maintenance & Features |
| **Safety Engine** | ✅ Verified | 6-part deterministic ARIMA safety gate; fails closed on volatility or threshold breach. | High Invariance (Do Not Weaken) |
| **Executor Logic** | ✅ Verified by Tests | 3-step state machine (`stop` $\to$ `modify` $\to$ `start`) with automated rollback & architecture guards. | Needs Live Validation |
| **FastAPI / API Layer** | ✅ Existing & Tested | REST endpoints (`/api/chat`, `/api/sessions`, `/run`, `/health`) with in-memory session persistence. | Live SSE Streaming |
| **Local / Mock / Demo Operation** | ✅ Working | Full local demo flow operating with synthetic benchmark fleet and offline price cache. | Ready to Run Locally |
| **Real AWS EC2 Discovery** | ✅ AWS CLI Verified | Queries live running EC2 instances via `boto3.client('ec2').describe_instances()`. | Tested with AWS Credentials |
| **Real CloudWatch Telemetry** | ⏳ Needs Live E2E Verification | Live metric ingestion implemented in `co2ops_agent/e2e_readonly.py`; requires validation against real active EC2 workloads. | 🔴 **High Priority** |
| **Real Bedrock Inference** | ❌ Blocked by AWS Restriction | Bedrock client & agent loops ready; requires live AWS account quota and model access approval. | 🔴 **Critical Priority** |
| **Real AWS Mutation** | ❌ Not Yet Validated | Rightsizing state machine tested via mocked boto3; requires validation in live AWS sandbox/staging VPC. | 🔴 **High Priority** |
| **Public Deployment** | ⏳ Not Deployed | Containerized Docker setup exists; production cloud hosting (App Runner / ECS Fargate + CloudFront) needed. | 🟡 **Medium Priority** |

---

## 🎯 Priority Workstreams & What Work is Needed

Based on the status matrix above, here are the key areas where you can make immediate, high-impact contributions:

### 1. 🔴 Real Amazon Bedrock Model Access & Live Inference
*Current Status: ❌ Currently blocked by AWS account restriction*

- **The Problem**: The Bedrock Converse API integration (`BedrockModelClient` and `BedrockAgent`) is completely implemented and passes all unit tests with mocks. However, running against live Bedrock endpoints requires an active AWS account with approved access to Anthropic Claude models.
- **Work Needed**:
  - **AWS Model Approvals**: Verify model enablement in the AWS Bedrock Console for:
    - `anthropic.claude-3-5-sonnet-20241022-v2:0` (or `us.anthropic.claude-3-5-sonnet-20241022-v2:0`)
    - `anthropic.claude-sonnet-4-6`
  - **Cross-Region Fallback**: Implement dynamic multi-region Bedrock routing (e.g., fallback from `us-east-1` to `us-west-2` or `eu-central-1` if Bedrock model throttling or service quotas occur).
  - **Multi-Turn Tool Verification**: Execute end-to-end multi-turn conversation traces with live Claude inference to ensure Bedrock's `toolUse` and `toolResult` parsing handles complex nested inputs smoothly.
  - **Streaming Token Response**: Integrate AWS Bedrock `ConverseStream` API with FastAPI Server-Sent Events (SSE) or WebSockets to deliver typewriter-style streaming responses to the frontend.

### 2. 🔴 Real CloudWatch Telemetry Live E2E Verification
*Current Status: ⏳ Needs live E2E verification*

- **The Problem**: A dedicated read-only end-to-end runner exists in [`co2ops_agent/e2e_readonly.py`](file:///d:/Projects/CO2Ops/co2ops_agent/e2e_readonly.py), and all unit tests pass with mocked CloudWatch metrics. We need live validation against a real AWS account with running EC2 instances emitting actual CloudWatch telemetry.
- **Work Needed**:
  - **Live Verification Run**: Run `python -m co2ops_agent.e2e_readonly` against an AWS account with active EC2 workloads and document the outputs.
  - **Provenance Guarantee Validation**: Confirm that when real CloudWatch metrics return $>0$ datapoints, the telemetry provenance flag accurately transitions from `demo` to `verified_live` and the deterministic safety gate evaluates properly.
  - **Handling Sparse Telemetry**: Improve handling of newly launched EC2 instances that have fewer than the required 5 historical CloudWatch datapoints (ensuring clear, user-friendly diagnostic logs).
  - **Extended Metric Collection**: Expand telemetry collection beyond CPU utilization to include:
    - Memory utilization (via AWS CloudWatch Agent metrics `mem_used_percent`).
    - EBS volume IOPS and throughput (`VolumeReadOps`, `VolumeWriteOps`).
    - Network interface traffic (`NetworkIn`, `NetworkOut`).

### 3. 🔴 Real AWS Mutation Validation in Sandbox
*Current Status: ❌ Not yet validated on live infrastructure*

- **The Problem**: The safe executor state machine in [`co2ops_agent/agents/safe_executor_agent/tools.py`](file:///d:/Projects/CO2Ops/co2ops_agent/agents/safe_executor_agent/tools.py) implements a hardened 3-step lifecycle:
  1. Verify instance state and CPU architecture (`x86_64` vs `arm64`).
  2. Safely stop the instance with boto3 waiters (`instance_stopped`).
  3. Modify the machine type attribute (`modify_instance_attribute`) and restart (`instance_running`).
  4. Automatically rollback and restore original running state if any modification error occurs.
  *This logic has been thoroughly tested via mocks and unit tests, but has not yet been executed on real live AWS instances.*
- **Work Needed**:
  - **Dedicated Sandbox Validation**: Spin up a throwaway AWS EC2 test instance (e.g., `t3.nano` or `t3.micro` in a sandbox VPC) and validate the complete live execution flow:
    ```bash
    # Safe execution test on test instance
    python -c "from co2ops_agent.agents.safe_executor_agent.tools import change_machine_type; print(change_machine_type('i-testinstanceid', 't3.small'))"
    ```
  - **Failure Rollback Injection**: Test transient network failure or IAM permission denial midway through execution to confirm that the instance is safely restarted and never left in an unrecoverable stopped state.
  - **EBS vs NVMe Compatibility**: Verify compatibility with instance storage types and Nitro-based hypervisor constraints when resizing across instance generations (e.g., `t2` $\to$ `t3`, `m4` $\to$ `m5`).
  - **Architectural Cross-Check Enforcement**: Validate that when attempting to resize an `x86_64` instance directly to an `arm64` Graviton target (`m6g.large`), the executor cleanly blocks the command with an informative architecture warning.

### 4. 🟡 Public Deployment & Infrastructure as Code (IaC)
*Current Status: ⏳ Not deployed*

- **The Problem**: CO2Ops currently runs locally via `run_local.ps1` or Docker Compose. A production-ready AWS deployment pipeline is needed so organizations can deploy CO2Ops into their own AWS accounts with minimal effort.
- **Work Needed**:
  - **Terraform / AWS CDK Modules**: Author IaC scripts that stand up:
    - AWS App Runner or ECS Fargate cluster for containerized backend execution.
    - S3 Bucket with CloudFront CDN distribution for static landing page & workspace hosting.
    - IAM Execution Roles with least-privilege policies (as specified in [`AWS_DEPLOYMENT_PLAN.md`](file:///d:/Projects/CO2Ops/AWS_DEPLOYMENT_PLAN.md)).
    - AWS Secrets Manager secret for Climatiq API key.
  - **Automated CI/CD Workflows**: Add GitHub Actions workflows (`.github/workflows/ci.yml`) to:
    - Run the complete 194-test suite on every Pull Request.
    - Run Python code linters (`ruff` / `flake8`) and formatters (`black`).
    - Build multi-arch Docker containers (`linux/amd64`, `linux/arm64`) and publish to Amazon ECR.
  - **Scheduled Telemetry Cron**: Deploy and test the AWS SAM template [`aws_lambda/template.yaml`](file:///d:/Projects/CO2Ops/aws_lambda/template.yaml) with Amazon EventBridge for automated daily snapshot ingestion.

### 5. 🟢 Frontend & User Experience Enhancements
*Current Status: ✅ Working locally, opportunities for polish*

- **Work Needed**:
  - **Live Streaming Chat**: Connect `Frontend/workspace.html` to a streaming backend endpoint for character-by-character agent responses.
  - **In-Console Presentation Deck Viewer**: Display rendered thumbnail previews and direct download buttons for `.pptx` presentations generated by `@summary_generator_agent`.
  - **Fleet Filter Controls**: Allow operators to select specific AWS regions (`us-east-1`, `eu-west-1`, etc.) or filter instances by AWS tag (e.g., `Environment=Production`, `Owner=FinOps`) directly from the UI.
  - **Interactive Forecast Curves**: Enhance the analytics chart visualization in `workspace.html` using Chart.js or ECharts with confidence interval bands for 7-day ARIMA predictions.

---

## 🛠️ Local Development Setup

To start contributing code locally:

### 1. Prerequisites
- **Python 3.12+** (tested through Python 3.14)
- **Git**
- **AWS CLI** (optional, for live AWS operations)

### 2. Fork & Clone
```bash
git clone https://github.com/<your-username>/GreenOps.git
cd GreenOps
```

### 3. Create Virtual Environment & Install Dependencies
```bash
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r co2ops_agent/requirements.txt
pip install pytest pytest-mock flake8 black

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r co2ops_agent/requirements.txt
pip install pytest pytest-mock flake8 black
```

### 4. Configure Environment Variables
Copy the example environment configuration:
```bash
cp co2ops_agent/.env.example co2ops_agent/.env
```
Edit `co2ops_agent/.env`:
```ini
AWS_DEFAULT_REGION=us-east-1
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-3-5-sonnet-20241022-v2:0
CLIMATIQ_API_KEY=your_key_here
```
*(Note: If you do not have live AWS credentials, CO2Ops operates seamlessly with built-in mock telemetry and cached pricing data).*

### 5. Run the Test Suite
Ensure all existing tests pass before making any changes:
```bash
pytest tests/ -v --disable-warnings
```

### 6. Start the Local Application
```powershell
# Windows
.\run_local.ps1
```
Or manually in two terminals:
```bash
# Terminal 1: Backend FastAPI Server
python -m uvicorn co2ops_agent.api:app --port 8080 --host 127.0.0.1

# Terminal 2: Frontend Web Server
cd Frontend
python -m http.server 8501
```
Access the application:
- **Landing Page**: `http://127.0.0.1:8501/`
- **Agent Workspace**: `http://127.0.0.1:8501/workspace.html`
- **API Swagger Docs**: `http://127.0.0.1:8080/docs`

---

## 📐 Contribution Guidelines & Architecture Principles

To maintain the production-grade quality, security, and mathematical reliability of CO2Ops, all contributors must adhere to the following principles:

### 1. Invariance of the Deterministic Safety Engine
The safety engine in [`co2ops_agent/agents/safe_executor_agent/tools.py`](file:///d:/Projects/CO2Ops/co2ops_agent/agents/safe_executor_agent/tools.py) is mathematically proven to prevent cloud workload latency and downtime.
- **NEVER** bypass, relax, or disable the safety thresholds (`MAX_CPU_AVG = 30.0`, `MAX_MEM_AVG = 40.0`, `MAX_CPU_P95 = 45.0`, `MAX_CPU_PEAK = 70.0`, `MAX_CPU_VOLATILITY = 15.0`).
- The Safety Gate **must always fail closed**: missing data, unparsable data, or synthetic fallback data during live production execution must immediately trigger a `BLOCK` decision.
- Claude / LLM reasoning must never override a mathematical safety gate block.

### 2. Strict AWS-Native Architecture
- CO2Ops is built exclusively on standard AWS services: **Amazon Bedrock**, **Amazon EC2**, **Amazon CloudWatch**, **AWS Pricing API**, and **Amazon S3**.
- Do not introduce Google ADK, proprietary vendor agent frameworks, or unnecessary external cloud dependencies.

### 3. Rigorous Telemetry Provenance
- Every piece of infrastructure data must carry provenance tracking (`provenance: 'verified_live'` vs `'demo'`, `telemetry_verified: bool`).
- Automated resizing must never mutate instances whose metrics are flagged as synthetic or demo.

### 4. Test-Driven Development (TDD)
- Any new agent, tool, or endpoint must be accompanied by comprehensive tests under `tests/`.
- Maintain 100% pass rate on the automated test suite (`pytest tests/`).

---

## 🔄 Pull Request Workflow

1. **Create a Topic Branch**:
   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```
2. **Make Your Changes**:
   Follow PEP 8 styling. Format code with `black` and check with `flake8`.
3. **Verify Tests**:
   Run `pytest tests/` and ensure all tests pass.
4. **Commit Your Changes**:
   Use descriptive, conventional commit messages:
   ```bash
   git commit -m "feat(bedrock): add cross-region failover handler for Claude converse API"
   ```
5. **Push and Open a PR**:
   Push your branch to your GitHub fork and open a Pull Request against `main`. Fill out the PR description template detailing:
   - What changed
   - Which status area or workstream this addresses
   - Proof of testing (command outputs or screenshots)

---

## 💬 Community & Questions

Have questions, suggestions, or want to discuss an implementation before writing code?
- Open a GitHub Issue for feature proposals or bug reports.
- Refer to [`AWS_DEPLOYMENT_PLAN.md`](file:///d:/Projects/CO2Ops/AWS_DEPLOYMENT_PLAN.md) for architectural specifications.
- Check [`Readme.md`](file:///d:/Projects/CO2Ops/Readme.md) for comprehensive system documentation.

Thank you for contributing to greener, more sustainable cloud operations! 🌍
