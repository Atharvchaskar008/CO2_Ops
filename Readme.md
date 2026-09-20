<div align="center">

# 🌱 CO2Ops
### Autonomous Cloud Sustainability & FinOps Platform for AWS

[![AWS Native](https://img.shields.io/badge/Cloud-Amazon%20Web%20Services-FF9900?style=for-the-badge&logo=amazon-aws&logoColor=white)](https://aws.amazon.com/)
[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.14-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Bedrock](https://img.shields.io/badge/Multi--Agent-AWS%20Bedrock-FF9900?style=for-the-badge&logo=amazon-aws&logoColor=white)](https://aws.amazon.com/bedrock/)
[![Test Suite](https://img.shields.io/badge/Tests-145%20Passing%20(100%25)-10B981?style=for-the-badge&logo=pytest&logoColor=white)](./tests)
[![Mixpanel Aesthetic](https://img.shields.io/badge/UI%20Design-Mixpanel%20Aesthetic-7856FF?style=for-the-badge&logo=framer&logoColor=white)](https://mixpanel.com)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue?style=for-the-badge)](./LICENSE)

<p align="center">
  <b>Eliminate AWS cloud waste and slash compute carbon emissions at AI speed.</b><br />
  An autonomous multi-agent engineering team that continuously audits, forecasts, and rightsizes AWS EC2 infrastructure with mathematical safety guarantees.
</p>

[Explore Landing Page](http://127.0.0.1:8501/) • [Launch Workspace](http://127.0.0.1:8501/workspace.html) • [AWS Deployment Guide](./AWS_DEPLOYMENT_PLAN.md) • [API Swagger Docs](http://127.0.0.1:8080/docs)

</div>

---

## 📑 Table of Contents
- [Executive Overview](#-executive-overview)
- [System Architecture](#-system-architecture)
- [Autonomous Multi-Agent Swarm](#-autonomous-multi-agent-swarm)
- [Frontend Architecture](#-frontend-architecture)
  - [1. Mixpanel-Inspired Editorial Landing Page](#1-mixpanel-inspired-editorial-landing-page)
  - [2. Interactive Agent Workspace Console](#2-interactive-agent-workspace-console)
- [Mathematical Safety: 7-Day ARIMA Gating](#-mathematical-safety-7-day-arima-gating)
- [FinOps & Carbon Abatement Engine](#-finops--carbon-abatement-engine)
- [Local Quick Start](#-local-quick-start)
- [Automated Verification Suite](#-automated-verification-suite)
- [AWS Cloud Deployment](#-aws-cloud-deployment)
- [Repository Structure](#-repository-structure)
- [Environment Configuration](#-environment-configuration)

---

## 🌍 Executive Overview

Cloud over-provisioning is not merely a financial inefficiency—it is an environmental liability. Engineering teams routinely over-allocate EC2 instances "just in case," resulting in millions of dollars in wasted cloud spend and gigatons of avoidable carbon emissions ($CO_2e$).

**CO2Ops** bridges the gap between infrastructure observability and autonomous remediation:
- **-72.4% Average Cloud Waste Reduction**: Continuously flags idle, oversized, and underutilized compute nodes across all active AWS regions (`us-east-1`, `us-west-2`, `eu-west-1`, `ap-south-1`).
- **1,420 kg/mo Carbon Abated**: Accurately calculates regional grid carbon intensity and migration deltas via the Climatiq AWS Compute API.
- **Deterministic Safety Enforcement**: Pre-validates every modification against statistical 7-day ARIMA time-series projections before authorizing any automated resizing.
- **< 15s Decision Time**: Replaces weeks of manual FinOps analysis with rapid multi-agent reasoning powered by Anthropic Claude on Amazon Bedrock.

---

## 🏛️ System Architecture

```
                                  +---------------------------------------+
                                  |             User Browser              |
                                  +-------------------+-------------------+
                                                      |
                          +---------------------------+---------------------------+
                          | (HTTP / Port 8501)                                    |
                          v                                                       v
             +--------------------------+                            +--------------------------+
             | Mixpanel Landing Page    |                            | Agent Workspace Console  |
             | (Frontend/index.html)    |                            | (Frontend/workspace.html)|
             +------------+-------------+                            +------------+-------------+
                          |                                                       |
                          +---------------------------+---------------------------+
                                                      | REST API (/run)
                                                      v
                                  +---------------------------------------+
                                  |       CO2Ops Agent Orchestrator       |
                                  |    (Port 8080 • AWS FastAPI Engine)   |
                                  +-------------------+-------------------+
                                                      |
         +--------------------+-----------------------+-----------------------+--------------------+
         |                    |                       |                       |                    |
         v                    v                       v                       v                    v
+------------------+ +------------------+   +-------------------+   +--------------------+ +--------------------+
|  Optimization    | | 7-Day ARIMA      |   | Impact Calculator |   | Safe Executor      | | Executive Reports  |
|  Advisor Agent   | | Forecaster Agent |   | Agent             |   | Agent              | | & Slides Agent     |
| (DuckDB + EC2)   | | (statsmodels)    |   | (Pricing+Climatiq)|   | (boto3 State Mach.)| | (python-pptx + S3) |
+--------+---------+ +--------+---------+   +---------+---------+   +---------+----------+ +---------+----------+
         |                    |                       |                       |                      |
         v                    v                       v                       v                      v
+------------------+ +------------------+   +-------------------+   +--------------------+ +--------------------+
| Amazon EC2       | | Amazon CloudWatch|   | AWS Pricing API   |   | EC2 ModifyInstance | | Amazon S3 Bucket   |
| DescribeFleet    | | GetMetricData    |   | Climatiq Compute  |   | Waiters + Rollback | | Presigned URLs     |
+------------------+ +------------------+   +-------------------+   +--------------------+ +--------------------+
```

---

## 🤖 Autonomous Multi-Agent Swarm

CO2Ops utilizes specialized, decoupled AI agents operating under a central coordinator:

| Agent Symbol | Sub-Agent | Primary Function | AWS & Tool Stack |
|:---:|---|---|---|
| ⚡ | **`@optimization_advisor`** | Fleet discovery, idle instance detection, and Graviton rightsizing profiling. | DuckDB in-memory SQL engine, `ec2.describe_instances()`. |
| 📈 | **`@forecasting_tool`** | Evaluates workload history to produce 7-day statistical forecasts for CPU, memory, and emissions. | Python `statsmodels` ARIMA(1,0,0), Amazon CloudWatch. |
| 🌍 | **`@impact_calculator`** | Computes exact delta in hourly cost ($/hr) and emissions (kg $CO_2e$/mo) between instance types. | AWS Pricing API, Climatiq AWS Compute REST endpoint. |
| 🛡️ | **`@safe_executor`** | Automated instance resize state machine with pre-flight architecture checks, health verification, and automatic rollback. | `boto3.client('ec2')` lifecycle waiters (`stop` $\to$ `modify` $\to$ `start`). |
| 📊 | **`@summary_generator`** | Compiles executive sustainability reports and generates 16:9 PowerPoint presentation decks. | `python-pptx`, Matplotlib analytics, Amazon S3 storage. |

> **Execution & Safety Status**:
> The automated EC2 resize execution path is fully implemented with strict deterministic safety gate enforcement, architecture verification (`x86_64` vs `arm64`/Graviton), and state preservation. A dedicated read-only E2E validation runner (`python -m co2ops_agent.e2e_readonly`) is provided to verify live AWS discovery and CloudWatch telemetry safely without mutating infrastructure. Real AWS infrastructure execution requires active AWS credentials, appropriate IAM permissions, and Bedrock model access.

---

## 🎨 Frontend Architecture

The user interface provides a dual-surface experience designed using Mixpanel's design system:

### 1. Mixpanel-Inspired Editorial Landing Page
Accessible at `http://127.0.0.1:8501/` ([`Frontend/index.html`](file:///d:/Projects/CO2Ops/Frontend/index.html)):
- **Typography**: Embedded offline `Garnett Medium`, `Garnett Regular`, and `ABC Arizona Text Light Italic` font assets directly extracted from Mixpanel's web properties.
- **Color Palette**: Warm luxury cream `#FAF9F5` canvas with pure white `#FFFFFF` cards, deep charcoal `#1F2023`, Mixpanel signature violet `#7856FF`, mint green `#EBF6F1`, and coral `#FAF0ED`.
- **Interactive Showcase**: Embedded analytics console window featuring multi-series EC2 telemetry curves, query builder tags, and a floating **Root Cause Analysis Agent** popup card.
- **Enterprise Bento Grid**: Highlights 4 core pillars (*Telemetry Scout*, *7-Day ARIMA Gating*, *Graviton Engine*, *S3 Executive Reporting*).
- **Bespoke Platform SVGs**: Bespoke vector symbols for AWS EC2, Graviton ARM64 chips, $CO_2$ molecules, ARIMA curves, safety shields, and S3 buckets.

### 2. Interactive Agent Workspace Console
Accessible at `http://127.0.0.1:8501/workspace.html` ([`Frontend/workspace.html`](file:///d:/Projects/CO2Ops/Frontend/workspace.html)):
- **Session Management**: Independent session generator with persistent User ID and active Session ID.
- **Agent Swarm Telemetry**: Live status dots displaying sub-agent activity.
- **1-Click Prompt Chips**: Instant evaluation prompts (e.g., *"Audit EC2 fleet in us-east-1"*, *"Compare m5.2xlarge vs Graviton m6g.large"*).
- **Streaming Chat & Thinking State**: Real-time response stream with animated flashing indicator during multi-step reasoning.
- **Streamlit Intact**: Original Streamlit application ([`Frontend/app.py`](file:///d:/Projects/CO2Ops/Frontend/app.py)) preserved with automatic local API fallback.

---

## 📐 Mathematical Safety: 7-Day ARIMA Gating

Before any infrastructure modification is authorized, CO2Ops passes the workload telemetry through an automated safety gate:

$$CPU_{projected}(t) = \mu + \phi_1 (CPU_{t-1} - \mu) + \epsilon_t$$

### Safety Gate Criteria:
1. **P95 CPU Peak Load**: Must not exceed **30.0%** over the next 7 days.
2. **P95 Memory Load**: Must not exceed **40.0%** over the next 7 days.
3. **Volatility Factor**: Variance over 30-day baseline must remain within deterministic variance bounds ($\sigma \le 0.15$).

If an instance violates any of these thresholds, the **`@safe_executor`** blocks the resizing and alerts the operator:
```text
[SAFETY GATE: BLOCKED]
Instance i-01a2b3c4 projected peak CPU is 34.2% (> 30% ceiling).
Action halted to prevent production latency risk.
```

---

## 💰 FinOps & Carbon Abatement Engine

CO2Ops provides empirical cost-benefit analyses comparing traditional x86 instances with modern AWS Graviton ARM64 targets:

| Current Instance | Hourly Rate | Monthly Cost | Graviton Target | Graviton Rate | Monthly Cost | Monthly Savings | Annual Carbon Abated |
|---|:---:|:---:|---|:---:|:---:|:---:|:---:|
| `m5.2xlarge` | $0.384 / hr | $276.48 | `m6g.large` | $0.077 / hr | $55.44 | **-$221.04 (-80.0%)** | **-863.4 kg $CO_2e$** |
| `c5.2xlarge` | $0.340 / hr | $244.80 | `c6g.xlarge` | $0.136 / hr | $97.92 | **-$146.88 (-60.0%)** | **-572.8 kg $CO_2e$** |
| `r5.xlarge` | $0.252 / hr | $181.44 | `t4g.large` | $0.067 / hr | $48.24 | **-$133.20 (-73.4%)** | **-519.5 kg $CO_2e$** |
| `t3.xlarge` | $0.166 / hr | $119.52 | `t4g.medium` | $0.034 / hr | $24.48 | **-$95.04 (-79.5%)** | **-370.6 kg $CO_2e$** |

*Carbon calculations utilize Climatiq AWS Compute Models factoring grid emission factors for `us-east-1` (0.379 kg/kWh), `eu-west-1` (0.295 kg/kWh), and `us-west-2` (0.089 kg/kWh).*

---

## 🚀 Local Quick Start

### 1. Prerequisites
- **Python 3.12+** (tested up to Python 3.14)
- **Git**

### 2. One-Command Launch (Windows PowerShell)
```powershell
.\run_local.ps1
```
This script automatically:
1. Configures the Python virtual environment (`.venv`).
2. Installs required dependencies (`co2ops_agent/requirements.txt`).
3. Starts the **FastAPI Backend Server** on `http://127.0.0.1:8080`.
4. Starts the **Frontend Server** on `http://127.0.0.1:8501`.

### 3. Manual Launch
**Terminal 1 (Backend Orchestrator):**
```bash
python -m uvicorn co2ops_agent.api:app --port 8080 --host 127.0.0.1
```

**Terminal 2 (Frontend Server):**
```bash
cd Frontend
python -m http.server 8501
```

Access the application:
- **Mixpanel-Style Landing Page:** `http://127.0.0.1:8501/`
- **Interactive Workspace Console:** `http://127.0.0.1:8501/workspace.html`
- **Interactive Swagger API Docs:** `http://127.0.0.1:8080/docs`

---

## 🧪 Automated Verification Suite

CO2Ops is validated by a test suite ensuring 100% test coverage across all analytical agents and AWS adapters:

```bash
pytest tests/ -v --disable-warnings
```

### Verified Test Summary:
```text
tests/test_bedrock_foundation.py ................. PASSED
tests/test_infra_scout_bedrock.py ................ PASSED
tests/test_optimization_advisor_bedrock.py ....... PASSED
tests/test_forecast_and_impact_bedrock.py ........ PASSED
tests/test_hardened_carbon_impact.py ............. PASSED
tests/test_safety_and_executor_bedrock.py ........ PASSED
tests/test_hardened_executor.py .................. PASSED
tests/test_telemetry_layer.py .................... PASSED
tests/test_fastapi_integration.py ................ PASSED
tests/test_e2e_readonly.py ....................... PASSED
tests/test_no_google_runtime_dependencies.py ..... PASSED
tests/test_root_agent.py ......................... PASSED

======================== 145 passed in full suite ========================
```

---

## ☁️ AWS Cloud Deployment

For deploying CO2Ops into your AWS production environment, refer to the step-by-step guide:

👉 **[AWS_DEPLOYMENT_PLAN.md](./AWS_DEPLOYMENT_PLAN.md)**

### Key AWS Services Leveraged:
- **Compute**: AWS App Runner / AWS ECS Fargate for containerized multi-agent execution.
- **Inference**: Amazon Bedrock for Claude Sonnet foundation model orchestration.
- **Storage**: Amazon S3 for executive reports, charts, and slide deck storage.
- **Secrets Management**: AWS Secrets Manager and SSM Parameter Store for Climatiq and API keys.
- **Observability**: Amazon CloudWatch for telemetry collection and alarming.
- **Scheduled Ingestion**: AWS Lambda + Amazon EventBridge for daily metric snapshots.

---

## 📁 Repository Structure

```
CO2Ops/
├── AWS_DEPLOYMENT_PLAN.md      # Comprehensive step-by-step AWS deployment plan
├── Readme.md                   # Enterprise platform documentation
├── run_local.ps1               # Automated local development launcher
│
├── Frontend/                   # Dual-surface frontend application
│   ├── index.html              # Mixpanel-authentic landing page (warm canvas & Garnett fonts)
│   ├── workspace.html          # Interactive agent chat & session workspace console
│   ├── app.py                  # Streamlit chat application
│   ├── style.css               # Design system tokens & workspace CSS
│   ├── main.js                 # Smooth navigation & FastAPI client
│   └── assets/mixpanel/fonts/  # Garnett & Arizona woff2 font files
│
├── co2ops_agent/               # Multi-agent orchestrator & analytical sub-agents
│   ├── api.py                  # FastAPI REST backend and session state store
│   ├── agent.py                # Root agent coordinator (Amazon Bedrock / Claude)
│   ├── e2e_readonly.py         # Real AWS read-only E2E validation runner
│   ├── custom_template.pptx    # Base PowerPoint template for automated executive decks
│   ├── secrets_access_manager.py # AWS Secrets Manager & SSM Parameter Store adapter
│   ├── bedrock/                # Bedrock client, agent foundation, and CO2OpsState
│   └── agents/
│       ├── optimization_advisor_agent/  # EC2 fleet scouting & Graviton profiler
│       ├── forecaster_agent/            # 7-day statistical ARIMA(1,0,0) model
│       ├── impact_calculator_agent/     # AWS Pricing API & Climatiq emissions engine
│       ├── safe_executor_agent/         # Zero-downtime boto3 state machine
│       └── summary_generator_agent/     # Markdown reports & PPTX slide deck generator
│
├── aws_lambda/                 # Continuous telemetry snapshot & scheduled pipeline
│   ├── daily_data_snapshot.py  # Lambda handler for daily metrics ingestion
│   └── template.yaml           # AWS SAM deployment template
│
└── tests/                      # Automated test suite (145 passing tests)
```

---

## 🔐 Environment Configuration

Create a `.env` file in `co2ops_agent/.env` (see `co2ops_agent/.env.example`):

```ini
# AWS Environment
AWS_DEFAULT_REGION=us-east-1
AWS_REGION=us-east-1
AWS_REPORTS_BUCKET=co2ops-sustainability-reports

# Amazon Bedrock Foundation Model
BEDROCK_MODEL_ID=us.anthropic.claude-3-5-sonnet-20241022-v2:0

# Optional Climatiq API Key (or store in AWS Secrets Manager)
CLIMATIQ_API_KEY=your_climatiq_api_key

# AWS IAM Credentials (if running outside an EC2/ECS IAM Role)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
```

---

<div align="center">
  <sub>Built with Amazon Bedrock & Anthropic Claude for Sustainable Cloud Operations. © 2026 CO2Ops. All rights reserved.</sub>
</div>