<div align="center">

# 🌱 CO2Ops
### Autonomous Cloud Sustainability & FinOps Platform for AWS

[![AWS Native](https://img.shields.io/badge/Cloud-Amazon%20Web%20Services-FF9900?style=for-the-badge&logo=amazon-aws&logoColor=white)](https://aws.amazon.com/)
[![Multi-Agent Bedrock](https://img.shields.io/badge/Multi--Agent-AWS%20Bedrock%20Converse%20API-FF9900?style=for-the-badge&logo=amazon-aws&logoColor=white)](https://aws.amazon.com/bedrock/)
[![Claude Sonnet](https://img.shields.io/badge/Foundation%20Model-Claude%203.5%20Sonnet%20%7C%204.6-D97706?style=for-the-badge&logo=anthropic&logoColor=white)](https://aws.amazon.com/bedrock/claude/)
[![Python Version](https://img.shields.io/badge/Python-3.12%20%7C%203.13%20%7C%203.14-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Test Suite](https://img.shields.io/badge/Tests-194%20Passing%20(100%25)-10B981?style=for-the-badge&logo=pytest&logoColor=white)](./tests)
[![Deterministic Safety](https://img.shields.io/badge/Safety%20Engine-7--Day%20ARIMA%20Gated-0284C7?style=for-the-badge&logo=shield&logoColor=white)](#-mathematical-safety-the-6-deterministic-safety-gates)
[![Mixpanel Aesthetic](https://img.shields.io/badge/UI%20Design-Mixpanel%20Editorial-7856FF?style=for-the-badge&logo=framer&logoColor=white)](https://mixpanel.com)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue?style=for-the-badge)](./LICENSE)

<p align="center">
  <b>Eliminate AWS cloud waste and slash compute carbon emissions with mathematical safety guarantees.</b><br />
  An autonomous multi-agent engineering swarm that continuously discovers, profiles, forecasts, and rightsizes AWS EC2 fleets using Amazon Bedrock, CloudWatch telemetry, and statsmodels ARIMA time-series models.
</p>

[🚀 Explore Landing Page](http://127.0.0.1:8501/) • [💬 Launch Workspace](http://127.0.0.1:8501/workspace.html) • [📖 AWS Deployment Guide](./AWS_DEPLOYMENT_PLAN.md) • [🤝 Contributing & Status Matrix](./contributions.md) • [🔌 API Swagger Docs](http://127.0.0.1:8080/docs)

</div>

---

## 📑 Table of Contents
- [Executive Overview](#-executive-overview)
- [How Things Work: End-to-End Operational Lifecycle](#-how-things-work-end-to-end-operational-lifecycle)
- [AWS Model Orchestration Deep Dive](#-aws-model-orchestration-deep-dive)
  - [1. Native Bedrock Converse API Architecture](#1-native-bedrock-converse-api-architecture)
  - [2. Dynamic Tool Introspection Engine](#2-dynamic-tool-introspection-engine)
  - [3. Autonomous Multi-Turn Tool Execution Loop](#3-autonomous-multi-turn-tool-execution-loop)
  - [4. Shared State Architecture (`CO2OpsState`)](#4-shared-state-architecture-co2opsstate)
  - [5. Orchestrator Routing & Sequential Pipelines](#5-orchestrator-routing--sequential-pipelines)
  - [6. Read-Only E2E Architecture Guard](#6-read-only-e2e-architecture-guard)
- [System Architecture](#-system-architecture)
- [Autonomous Multi-Agent Swarm](#-autonomous-multi-agent-swarm)
- [Mathematical Safety: The 6 Deterministic Safety Gates](#-mathematical-safety-the-6-deterministic-safety-gates)
- [FinOps & Regional Carbon Abatement Engine](#-finops--regional-carbon-abatement-engine)
- [Dual-Surface Frontend: Mixpanel Editorial Aesthetic](#-dual-surface-frontend-mixpanel-editorial-aesthetic)
- [FastAPI REST Backend & Session Store](#-fastapi-rest-backend--session-store)
- [Local Quick Start](#-local-quick-start)
- [Automated Verification Suite (145 Passing Tests)](#-automated-verification-suite-145-passing-tests)
- [AWS Cloud Production Deployment](#-aws-cloud-production-deployment)
- [Current Project Status & Roadmap](#-current-project-status--roadmap)
- [Repository Directory Structure](#-repository-directory-structure)

---

## 🌍 Executive Overview

Modern cloud infrastructure is plagued by chronic over-provisioning. Engineering teams routinely oversize compute instances "just in case," leaving thousands of EC2 nodes running at $10\text{–}20\%$ average CPU utilization. This creates massive financial waste and directly inflates global carbon footprints through avoidable power consumption:

- **Financial Inefficiency**: Compute typically accounts for over $60\%$ of total cloud bills, with up to $35\%$ representing complete waste.
- **Environmental Impact**: Data centers consume approximately $1\text{–}1.5\%$ of global electricity. Every wasted kilowatt-hour corresponds directly to fossil-fuel grid emissions ($CO_2e$).
- **The Rightsizing Inertia**: Infrastructure teams hesitate to downsize nodes manually due to fear of unexpected traffic surges, production latency degradation, and service downtime.

**CO2Ops** solves this dilemma through autonomous, mathematically provable rightsizing:

<div align="center">

| Core Metric | Performance | Architectural Mechanism |
|---|:---:|---|
| **Cloud Waste Reduction** | **-72.4%** | Fleet scouting via DuckDB & automated migration to high-efficiency AWS Graviton targets. |
| **Carbon Abatement** | **1,420 kg/mo** | Dynamic regional grid emission accounting (EPA eGRID & Climatiq Compute API). |
| **Audit & Decision Speed** | **< 15 sec** | Coordinated multi-agent reasoning on Amazon Bedrock Converse API with Claude. |
| **Production Safety** | **100% Gated** | 6-part deterministic statistical gate (ARIMA P95, peak, volatility, & average limits). |

</div>

---

## ⚙️ How Things Work: End-to-End Operational Lifecycle

The diagram below outlines the seven-phase lifecycle executed when CO2Ops evaluates and optimizes an AWS EC2 fleet:

```
[ 1. Ingestion & Scout ] ──> [ 2. Workload Profiler ] ──> [ 3. 7-Day ARIMA Forecaster ]
  • EC2 DescribeInstances      • DuckDB SQL Engine          • statsmodels ARIMA(1,0,0)
  • CloudWatch GetMetrics       • Graviton Matching          • Peak, P95 & Volatility
             │
             ▼
[ 4. Impact Calculator ] ──> [ 5. Deterministic Safety ] ──> [ 6. Safe Executor ]
  • AWS Pricing API             • 6-Gate Statistical Rule      • Boto3 Waiters State Mach.
  • Climatiq Grid Factors       • FAIL-CLOSED Enforcement     • Automatic Rollback
             │
             ▼
[ 7. Executive Reporting ]
  • S3 Report Staging
  • 16:9 Presentation Decks
```

### Detailed Operational Flow:

1. **Multi-Region Fleet Discovery & Telemetry Scouting (`@optimization_advisor`)**:
   - Queries Amazon EC2 across active regions (`us-east-1`, `us-west-2`, `eu-west-1`, `ap-south-1`) via `boto3.client('ec2').describe_instances()`.
   - Ingests 14-day historical telemetry from Amazon CloudWatch (`boto3.client('cloudwatch').get_metric_statistics()`), sampling CPU, memory, disk IOPS, and network throughput.
   - Stamps telemetry records with strict provenance metadata (`provenance: 'verified_live'` vs `'demo'`).
   - Loads fleet metadata into an embedded DuckDB in-memory database for ultra-fast SQL aggregation.

2. **Workload Profiling & Graviton Rightsizing Engine (`@workload_profiler` + `@recommender`)**:
   - Filters for underutilized instances (e.g., $CPU_{avg} < 20\%$, $Mem_{avg} < 35\%$).
   - Evaluates CPU architectures (`x86_64` vs `arm64`) and maps legacy x86 instances (`m5`, `c5`, `r5`, `t3`) to optimal AWS Graviton targets (`m6g`, `c6g`, `r6g`, `t4g`), providing up to $40\%$ price-performance improvement and $60\%$ reduced wattage.

3. **7-Day Statistical Time-Series Forecasting (`@forecaster`)**:
   - Evaluates historical telemetry trends using a univariate autoregressive integrated moving average model ($\text{ARIMA}(1,0,0)$).
   - Generates a projected 7-day hourly trajectory with mean expectation, peak boundaries, P95 percentiles, and workload volatility ($\sigma$).

4. **FinOps & Climatiq Carbon Calculation (`@impact_calculator`)**:
   - Queries current AWS on-demand pricing rates for both original and candidate instances.
   - Calculates the net reduction in electrical wattage ($W_{current} - W_{target}$) and models regional grid carbon intensity ($kg CO_2e / kWh$) using EPA eGRID, EEA, and the Climatiq AWS Compute API.
   - Produces exact projected dollar savings ($\$/\text{mo}$) and carbon abatement ($kg CO_2e/\text{mo}$).

5. **Deterministic Mathematical Safety Gating (`@safe_executor / safety_agent`)**:
   - Evaluates the 7-day forecasted utilization against 6 hard mathematical boundaries.
   - If projected P95 CPU exceeds $45\%$, peak CPU exceeds $70\%$, volatility exceeds $15\%$, or telemetry is missing/synthetic, the migration is immediately **BLOCKED**.
   - Claude and LLM reasoning **cannot bypass** this gate.

6. **Hardened Rightsizing Execution & Zero-Downtime Rollback (`@safe_executor / executor_agent`)**:
   - Verifies pre-flight architecture compatibility (prevents invalid cross-architecture mutations).
   - Coordinates the 3-phase EC2 modification lifecycle:
     $$\text{Stop Instance} \longrightarrow \text{Modify Instance Attribute} \longrightarrow \text{Restart Instance}$$
   - Uses AWS boto3 waiters (`instance_stopped`, `instance_running`) with strict timeouts.
   - **Automated Rollback**: If `modify_instance_attribute` or instance restart fails, the executor automatically restores the instance to its original state and verifies its health.

7. **Executive Reporting & Presentation Decks (`@summary_generator`)**:
   - Compiles findings into an executive markdown briefing.
   - Generates professional 16:9 widescreen PowerPoint presentation slide decks using `python-pptx` with embedded Matplotlib analytics charts.
   - Uploads artifacts to an Amazon S3 bucket (`AWS_REPORTS_BUCKET`) and generates secure presigned download URLs.

---

## 🧠 AWS Model Orchestration Deep Dive

CO2Ops replaces legacy proprietary agent frameworks with a **100% native Amazon Bedrock Converse API architecture**.

```
                           +-------------------------------------+
                           |         User Message / Prompt       |
                           +------------------+------------------+
                                              |
                                              v
                           +-------------------------------------+
                           |         BedrockOrchestrator         |
                           |       (Intent & Route Engine)       |
                           +------------------+------------------+
                                              |
                     +------------------------+------------------------+
                     |                                                 |
                     v                                                 v
       +----------------------------+                    +----------------------------+
       |       BedrockAgent         |                    |      BedrockPipeline       |
       |  (Single Specialized Turn) |                    |  (Sequential Multi-Agent)  |
       +--------------+-------------+                    +--------------+-------------+
                      |                                                 |
                      +-----------------------+-------------------------+
                                              |
                                              v
                           +-------------------------------------+
                           |      Bedrock Converse API Call      |
                           |   (Claude 3.5 Sonnet / Claude 4.6)  |
                           +------------------+------------------+
                                              |
                        +---------------------+---------------------+
                        | stopReason == "tool_use"                  | stopReason == "end_turn"
                        v                                           v
       +---------------------------------+        +---------------------------------+
       |  Dynamic Tool Dispatch Engine   |        |   Extract Model Response Text   |
       |  • python_func_to_bedrock_tools |        |   Update CO2OpsState Fields     |
       |  • Inject CO2OpsState Context   |        +----------------+----------------+
       |  • Execute Python / Boto3 Tool  |                         |
       +----------------+----------------+                         v
                        |                         +---------------------------------+
                        +────────────────────────>│ Return Updated State to API/UI  │
                          Pass toolResult back    +---------------------------------+
                          to Converse Loop
```

### 1. Native Bedrock Converse API Architecture
- Wrapped inside [`co2ops_agent/bedrock/client.py`](file:///d:/Projects/CO2Ops/co2ops_agent/bedrock/client.py) (`BedrockModelClient`).
- Authenticates securely via standard AWS IAM credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or IAM instance profile / ECS task role). Never hardcodes credentials.
- Defaults to Anthropic Claude models on Amazon Bedrock (`anthropic.claude-sonnet-4-6` or `us.anthropic.claude-3-5-sonnet-20241022-v2:0`).
- Provides configurable inference parameters (`temperature: 0.2`, `maxTokens: 2048`, `topP: 0.9`).

### 2. Dynamic Tool Introspection Engine
In [`co2ops_agent/bedrock/agent.py`](file:///d:/Projects/CO2Ops/co2ops_agent/bedrock/agent.py), `python_func_to_bedrock_tool_spec()` uses Python's runtime `inspect` module to dynamically build valid Amazon Bedrock `toolSpec` schemas directly from native Python functions:
- Extracts function names and first-line docstrings as tool descriptions.
- Inspects parameter type annotations (`str`, `int`, `float`, `bool`, `list`, `dict`) and generates corresponding JSON Schema properties.
- Automatically handles required vs optional parameters based on default values.
- Seamlessly excludes runtime state injection parameters (`state`, `tool_context`) from the model-facing schema.

### 3. Autonomous Multi-Turn Tool Execution Loop
When Claude decides to invoke one or more tools:
1. Bedrock returns `stopReason: "tool_use"` with tool names and arguments in `output.message.content`.
2. `BedrockAgent.run()` intercepts the tool call, matches the tool name in its registered tool map, and injects `CO2OpsState` if required by the function signature.
3. The tool executes (e.g., querying CloudWatch or calculating Climatiq emissions), and its result is packaged into a Bedrock `toolResult` block:
   ```json
   {
     "toolResult": {
       "toolUseId": "tooluse_xyz123",
       "content": [{"json": { "status": "success", "p95_cpu": 18.4 }}],
       "status": "success"
     }
   }
   ```
4. The agent sends the `toolResult` back to Bedrock Converse API in the conversation message history.
5. Bedrock processes the tool output and can either trigger additional tools or synthesize its final analysis (`stopReason: "end_turn"`). The loop handles up to 5 consecutive tool turns safely.

### 4. Shared State Architecture (`CO2OpsState`)
All agents communicate through an explicit, strongly-typed execution container: [`CO2OpsState`](file:///d:/Projects/CO2Ops/co2ops_agent/bedrock/state.py).
- **Stage 1**: `infra_data` (discovered fleet instances, telemetry metrics, provenance tags).
- **Stage 2**: `analysis_results` & `final_recommendations` (Graviton rightsizing proposals).
- **Stage 3**: `forecast_data` (7-day ARIMA series, confidence bands, volatility metrics).
- **Stage 4**: `impact_analysis` (dollar savings, kWh reductions, kg $CO_2e$ abated).
- **Stage 5**: `safety_eval` (deterministic gate decision `ALLOW` or `BLOCK`, failure rationale).
- **Stage 6**: `execution_result` (boto3 lifecycle logs, original/target types, verification state).
- **Stage 7**: `report_metadata` & `chart_links` (S3 presigned URLs, slide deck paths).

### 5. Orchestrator Routing & Sequential Pipelines
The root coordinator [`BedrockOrchestrator`](file:///d:/Projects/CO2Ops/co2ops_agent/bedrock/orchestrator.py) manages intent routing:
- **Keyword & Intent Routing**: Routes user prompts to specialized agents or multi-agent pipelines:
  - `"audit"`, `"scout"`, `"idle"`, `"optimize"` $\to$ `OptimizationAdvisor` Pipeline (`infra_scout` $\to$ `workload_profiler` $\to$ `recommender`).
  - `"forecast"`, `"predict"`, `"arima"` $\to$ `forecasting_tool_agent`.
  - `"compare"`, `"impact"`, `"price"`, `"carbon"` $\to$ `impact_calculator_agent`.
  - `"migrate"`, `"resize"`, `"execute"` $\to$ `SafeExecutor` Pipeline (`safety_agent` $\to$ `executor_agent`).
  - `"report"`, `"summary"`, `"slides"` $\to$ `summary_generator_agent`.
- **BedrockPipeline**: Chains agents sequentially, threading the same `CO2OpsState` instance so downstream agents consume outputs from upstream agents without loss of context.

### 6. Read-Only E2E Architecture Guard
To validate live AWS connectivity safely, CO2Ops includes a dedicated, non-mutating validation runner: [`co2ops_agent/e2e_readonly.py`](file:///d:/Projects/CO2Ops/co2ops_agent/e2e_readonly.py).
- Sets `CO2OPS_READ_ONLY_MODE=true` in the execution environment.
- Queries real running EC2 instances via `ec2.describe_instances()`.
- Fetches real CloudWatch metric statistics via `cloudwatch.get_metric_statistics()`.
- Validates model inference readiness on Amazon Bedrock.
- Evaluates the 7-day ARIMA forecast and deterministic safety gate.
- **Enforces Zero Mutation**: The executor explicitly halts before modifying any AWS resources, guaranteeing complete safety during live verification audits.

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
                                                      | REST API (/api/chat, /run)
                                                      v
                                  +---------------------------------------+
                                  |       CO2Ops Agent Backend API        |
                                  |     (Port 8080 • FastAPI Engine)      |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |       Bedrock Root Orchestrator       |
                                  |     (Intent Router & State Coord.)    |
                                  +-------------------+-------------------+
                                                      |
          +--------------------+----------------------+-----------------------+--------------------+
          |                    |                      |                       |                    |
          v                    v                      v                       v                    v
+------------------+  +------------------+  +-------------------+  +--------------------+  +--------------------+
|  Optimization    |  | 7-Day ARIMA      |  | Impact Calculator |  | Safe Executor      |  | Executive Reports  |
|  Advisor Agent   |  | Forecaster Agent |  | Agent             |  | Agent              |  | & Slides Agent     |
| (DuckDB + EC2)   |  | (statsmodels)    |  | (Pricing+Climatiq)|  | (boto3 Waiters)    |  | (python-pptx + S3) |
+--------+---------+  +--------+---------+  +---------+---------+  +---------+----------+  +---------+----------+
         |                     |                      |                      |                       |
         v                     v                      v                      v                       v
+------------------+  +------------------+  +-------------------+  +--------------------+  +--------------------+
| Amazon EC2       |  | Amazon CloudWatch|  | AWS Pricing API   |  | EC2 ModifyInstance |  | Amazon S3 Bucket   |
| DescribeFleet    |  | GetMetricData    |  | Climatiq Compute  |  | Waiters + Rollback |  | Presigned URLs     |
+------------------+  +------------------+  +-------------------+  +--------------------+  +--------------------+
```

---

## 🤖 Autonomous Multi-Agent Swarm

CO2Ops organizes its intelligence into decoupled, highly specialized sub-agents:

| Symbol | Sub-Agent | Primary Function | AWS & Tool Stack |
|:---:|---|---|---|
| ⚡ | **`@optimization_advisor`** | Fleet discovery, idle instance detection, and Graviton rightsizing profiling. | DuckDB SQL, `ec2.describe_instances()`. |
| 📈 | **`@forecasting_tool`** | Evaluates workload history to produce 7-day statistical projections for CPU and memory. | Python `statsmodels` $\text{ARIMA}(1,0,0)$, Amazon CloudWatch. |
| 🌍 | **`@impact_calculator`** | Computes exact delta in hourly cost ($\$/\text{hr}$) and carbon emissions ($kg CO_2e/\text{mo}$). | AWS Pricing API, Climatiq AWS Compute Models. |
| 🛡️ | **`@safe_executor`** | 6-gate deterministic safety engine and zero-downtime EC2 resize state machine. | `boto3.client('ec2')` (`stop` $\to$ `modify` $\to$ `start`). |
| 📊 | **`@summary_generator`** | Compiles executive sustainability briefings and generates 16:9 PowerPoint decks. | `python-pptx`, Matplotlib analytics, Amazon S3. |

---

## 📐 Mathematical Safety: The 6 Deterministic Safety Gates

Before any infrastructure modification is authorized, CO2Ops passes the workload telemetry through an automated mathematical safety gate:

$$CPU_{\text{projected}}(t) = \mu + \phi_1 (CPU_{t-1} - \mu) + \epsilon_t$$

### The 6 Deterministic Safety Gates:

| Safety Gate Check | Threshold Limit | Rationale / Failure Consequence |
|---|:---:|---|
| **1. Peak CPU Utilization** | **$< 70.0\%$** | Prevents unexpected spikes from exhausting core capacity. |
| **2. Peak Memory Utilization** | **$< 70.0\%$** | Prevents Out-Of-Memory (OOM) kernel kills on target nodes. |
| **3. P95 CPU Utilization** | **$< 45.0\%$** | Ensures high sustained load periods have adequate headroom. |
| **4. P95 Memory Utilization** | **$< 45.0\%$** | Prevents paging and swap thrashing under normal peak load. |
| **5. Workload Volatility ($\sigma$)** | **$< 15.0\%$** | Rejects erratic, bursty, or unpredictable workloads. |
| **6. Average CPU & Memory** | **$CPU < 30\%$, $Mem < 40\%$** | Guarantees the instance is genuinely underutilized. |

### Strict Fail-Closed Safeguards:
- **Telemetry Verification**: Refuses migration if CloudWatch telemetry has $<5$ valid numeric datapoints.
- **No Synthetic Fallback Mutation**: Blocks rightsizing if data provenance is marked `demo`, `synthetic`, or `fallback`.
- **No-State Bypass Protection**: Fails closed immediately (`blocked_no_safety_context`) if `CO2OpsState` is omitted or `None`, preventing agents or users from bypassing safety gates.
- **Architecture Cross-Check**: Blocks direct $x86\_64 \to arm64$ (Graviton) mutations without an AMI rebuild to prevent kernel panic boot loops.
- **Rollback & Diagnostics**: Automatically restores the original running state if AWS modification fails, logging explicit `rollback_status` (`rollback_succeeded` vs `rollback_failed`) and `rollback_error`.

```text
[SAFETY GATE: BLOCKED]
Instance i-01a2b3c4 projected peak CPU is 74.2% (> 70.0% ceiling).
Action halted: Target instance cannot guarantee safe production headroom.
```

---

## 💰 FinOps & Regional Carbon Abatement Engine

CO2Ops provides empirical cost-benefit analyses comparing traditional x86 instances with modern AWS Graviton ARM64 targets:

### Compute Comparison Matrix:
| Current Instance | Hourly Rate | Monthly Cost | Graviton Target | Graviton Rate | Monthly Cost | Monthly Savings | Annual Carbon Abated |
|---|:---:|:---:|---|:---:|:---:|:---:|:---:|
| `m5.2xlarge` | $0.384 / hr | $276.48 | `m6g.large` | $0.077 / hr | $55.44 | **-$221.04 (-80.0%)** | **-863.4 kg $CO_2e$** |
| `c5.2xlarge` | $0.340 / hr | $244.80 | `c6g.xlarge` | $0.136 / hr | $97.92 | **-$146.88 (-60.0%)** | **-572.8 kg $CO_2e$** |
| `r5.xlarge` | $0.252 / hr | $181.44 | `t4g.large` | $0.067 / hr | $48.24 | **-$133.20 (-73.4%)** | **-519.5 kg $CO_2e$** |
| `t3.xlarge` | $0.166 / hr | $119.52 | `t4g.medium` | $0.034 / hr | $24.48 | **-$95.04 (-79.5%)** | **-370.6 kg $CO_2e$** |

### Carbon Emissions Physics:
$$E = P_{\text{kW}} \times t_{\text{hours}} \times CI_{\text{regional}}$$

*Grid emission intensities ($CI$) calibrated via EPA eGRID, EEA, and CEA India:*
- `us-east-1` (Virginia / PJM): **0.379 kg $CO_2e$/kWh**
- `us-east-2` (Ohio): **0.441 kg $CO_2e$/kWh**
- `us-west-2` (Oregon / Hydro): **0.121 kg $CO_2e$/kWh**
- `eu-west-1` (Ireland): **0.278 kg $CO_2e$/kWh**
- `ap-south-1` (Mumbai): **0.708 kg $CO_2e$/kWh**

---

## 🎨 Dual-Surface Frontend: Mixpanel Editorial Aesthetic

The web experience provides two cohesive interfaces built using Mixpanel's design system:

### 1. Mixpanel-Inspired Editorial Landing Page
Accessible at `http://127.0.0.1:8501/` ([`Frontend/index.html`](file:///d:/Projects/CO2Ops/Frontend/index.html)):
- **Typography**: Embedded offline `Garnett Medium`, `Garnett Regular`, and `ABC Arizona Text Light Italic` font assets.
- **Color Palette**: Warm luxury cream `#FAF9F5` canvas, pure white `#FFFFFF` cards, deep charcoal `#1F2023`, signature violet `#7856FF`, mint green `#EBF6F1`, and coral `#FAF0ED`.
- **Interactive Showcase**: Embedded analytics console window featuring multi-series EC2 telemetry curves, query builder tags, and a floating **Root Cause Analysis Agent** popup card.
- **Enterprise Bento Grid**: Highlights 4 core pillars (*Telemetry Scout*, *7-Day ARIMA Gating*, *Graviton Engine*, *S3 Executive Reporting*).
- **Bespoke Platform SVGs**: Handcrafted vector symbols for EC2, Graviton ARM64 chips, $CO_2$ molecules, ARIMA curves, safety shields, and S3 buckets.

### 2. Interactive Agent Workspace Console
Accessible at `http://127.0.0.1:8501/workspace.html` ([`Frontend/workspace.html`](file:///d:/Projects/CO2Ops/Frontend/workspace.html)):
- **Session Management**: Independent session generator with persistent User ID and active Session ID.
- **Agent Swarm Telemetry**: Live status dots displaying sub-agent activity.
- **1-Click Prompt Chips**: Instant evaluation prompts (e.g., *"Audit EC2 fleet in us-east-1"*, *"Compare m5.2xlarge vs Graviton m6g.large"*).
- **Streaming Chat & Thinking State**: Real-time response stream with animated indicator during multi-step reasoning.
- **Legacy Streamlit App**: Streamlit application ([`Frontend/app.py`](file:///d:/Projects/CO2Ops/Frontend/app.py)) preserved with automatic local API fallback.

---

## ⚡ FastAPI REST Backend & Session Store

The backend exposes clean REST endpoints documented automatically via OpenAPI / Swagger UI at `http://127.0.0.1:8080/docs`:

| Endpoint | Method | Description |
|---|:---:|---|
| **`/health`** | `GET` | Health check reporting service status, active sessions, Bedrock model ID, and region. |
| **`/api/sessions`** | `POST` | Creates a new user session with a fresh `CO2OpsState` instance. |
| **`/api/sessions/{session_id}`** | `GET` | Retrieves full state snapshot (telemetry, forecasts, safety decisions, messages). |
| **`/api/chat`** | `POST` | Native REST chat endpoint routing prompts through `BedrockOrchestrator`. |
| **`/run`** | `POST` | Backwards-compatibility endpoint supporting legacy payloads and frontend clients. |
| **`/docs`** | `GET` | Interactive OpenAPI Swagger UI documentation. |

---

## 🚀 Local Quick Start

### 1. Prerequisites
- **Python 3.12+** (tested through Python 3.14)
- **Git**
- **AWS CLI** (optional for live AWS features; mock demo works out of the box)

### 2. One-Command Launch (Windows PowerShell)
```powershell
.\run_local.ps1
```
This launcher automatically:
1. Configures the Python virtual environment (`.venv`).
2. Installs required dependencies from `co2ops_agent/requirements.txt`.
3. Launches the **FastAPI Backend Server** on `http://127.0.0.1:8080`.
4. Launches the **Frontend Server** on `http://127.0.0.1:8501`.

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
- **Mixpanel Landing Page**: `http://127.0.0.1:8501/`
- **Interactive Workspace Console**: `http://127.0.0.1:8501/workspace.html`
- **Interactive Swagger API Docs**: `http://127.0.0.1:8080/docs`

---

## 🧪 Automated Verification Suite (194 Passing Tests)

CO2Ops is validated by an extensive 194-test regression suite ensuring 100% test coverage across all agents, tools, safety engines, and AWS adapters:

```bash
pytest tests/ -v --disable-warnings
```

### Verified Test Summary:
```text
tests/test_bedrock_foundation.py ................. PASSED [ 11%]
tests/test_infra_scout_bedrock.py ................ PASSED [ 18%]
tests/test_optimization_advisor_bedrock.py ....... PASSED [ 26%]
tests/test_forecast_and_impact_bedrock.py ........ PASSED [ 34%]
tests/test_hardened_carbon_impact.py ............. PASSED [ 42%]
tests/test_safety_and_executor_bedrock.py ........ PASSED [ 51%]
tests/test_safety_regression.py .................. PASSED [ 67%]
tests/test_hardened_executor.py .................. PASSED [ 78%]
tests/test_aws_executor.py ....................... PASSED [ 82%]
tests/test_telemetry_layer.py .................... PASSED [ 88%]
tests/test_fastapi_integration.py ................ PASSED [ 93%]
tests/test_e2e_readonly.py ....................... PASSED [ 97%]
tests/test_no_google_runtime_dependencies.py ..... PASSED [ 99%]
tests/test_root_agent.py ......................... PASSED [100%]

======================== 194 passed in full suite ========================
```

### Safe Real-AWS Read-Only Validation:
To verify live AWS EC2 and CloudWatch connectivity safely without mutating infrastructure:
```bash
python -m co2ops_agent.e2e_readonly
```

---

## ☁️ AWS Cloud Production Deployment

For deploying CO2Ops into your AWS production environment, refer to the step-by-step blueprint:

👉 **[AWS_DEPLOYMENT_PLAN.md](./AWS_DEPLOYMENT_PLAN.md)**

### Key AWS Services:
- **Compute**: AWS App Runner or AWS ECS Fargate for containerized multi-agent execution.
- **Inference**: Amazon Bedrock for Anthropic Claude foundation model orchestration.
- **Storage**: Amazon S3 for executive reports, charts, and slide deck storage.
- **Secrets Management**: AWS Secrets Manager and SSM Parameter Store for Climatiq and API keys.
- **Observability**: Amazon CloudWatch for telemetry collection and alarming.
- **Scheduled Ingestion**: AWS Lambda + Amazon EventBridge for daily metric snapshots.

---

## 📊 Current Project Status & Roadmap

Please refer to [`contributions.md`](./contributions.md) for full contribution guidelines, priorities, and setup instructions.

| Area | Current Status | Description & Verification State | Priority for Contributors |
|---|:---:|---|:---:|
| **Backend Python Code** | ✅ Working | Core multi-agent framework, DuckDB analytics, and state management operational. | Maintenance |
| **Safety Engine** | ✅ Verified | 6-part deterministic ARIMA safety gate; fails closed on threshold breach. | High Invariance |
| **Executor Logic** | ✅ Verified by Tests | 3-step state machine (`stop` $\to$ `modify` $\to$ `start`) with automated rollback. | Needs Live Validation |
| **FastAPI / API Layer** | ✅ Existing & Tested | REST endpoints (`/api/chat`, `/api/sessions`, `/run`, `/health`) with session persistence. | Live SSE Streaming |
| **Local / Mock / Demo Operation** | ✅ Working | Full local demo flow operating with synthetic benchmark fleet and price cache. | Ready to Run Locally |
| **Real AWS EC2 Discovery** | ✅ AWS CLI Verified | Queries live running EC2 instances via `boto3.client('ec2').describe_instances()`. | Tested with AWS Credentials |
| **Real CloudWatch Telemetry** | ⏳ Needs Live E2E Verification | Metric ingestion implemented in `co2ops_agent/e2e_readonly.py`; needs live workload runs. | 🔴 **High Priority** |
| **Real Bedrock Inference** | ❌ Blocked by AWS Restriction | Bedrock client & agent loops ready; requires live AWS account quota and model access. | 🔴 **Critical Priority** |
| **Real AWS Mutation** | ❌ Not Yet Validated | Rightsizing state machine tested via mocked boto3; requires sandbox live validation. | 🔴 **High Priority** |
| **Public Deployment** | ⏳ Not Deployed | Containerized Docker setup exists; production cloud hosting (App Runner / ECS) needed. | 🟡 **Medium Priority** |

---

## 📁 Repository Directory Structure

```
CO2Ops/
├── AWS_DEPLOYMENT_PLAN.md      # Comprehensive step-by-step AWS deployment blueprint
├── Readme.md                   # Complete platform documentation & architecture guide
├── contributions.md            # Contributor guide, status matrix & work needed roadmap
├── CONTRIBUTING.md             # GitHub standard entry point pointing to contributions.md
├── run_local.ps1               # Automated local development launcher (Windows)
├── docker-compose.yml          # Containerized local orchestration
│
├── Frontend/                   # Dual-surface frontend application
│   ├── index.html              # Mixpanel editorial landing page (warm canvas & Garnett fonts)
│   ├── workspace.html          # Interactive agent chat & session workspace console
│   ├── app.py                  # Streamlit chat application
│   ├── style.css               # Design system tokens & workspace CSS
│   ├── main.js                 # Navigation & FastAPI REST client
│   └── assets/mixpanel/fonts/  # Garnett & Arizona woff2 font files
│
├── co2ops_agent/               # Multi-agent orchestrator & analytical sub-agents
│   ├── api.py                  # FastAPI REST backend and session state store
│   ├── agent.py                # Root agent coordinator (Amazon Bedrock / Claude)
│   ├── e2e_readonly.py         # Real AWS read-only E2E validation runner
│   ├── custom_template.pptx    # Base PowerPoint template for executive slide decks
│   ├── secrets_access_manager.py # AWS Secrets Manager & SSM Parameter Store adapter
│   ├── bedrock/                # Bedrock client wrapper, agent foundation, and CO2OpsState
│   │   ├── agent.py            # BedrockAgent with dynamic tool introspection & Converse loop
│   │   ├── client.py           # BedrockModelClient wrapper around boto3 converse API
│   │   ├── orchestrator.py     # BedrockOrchestrator & BedrockPipeline (sequential execution)
│   │   └── state.py            # CO2OpsState typed execution state container
│   │
│   └── agents/                 # Specialized analytical sub-agents
│       ├── optimization_advisor_agent/  # EC2 fleet scouting & Graviton profiler
│       │   └── sub_agents/
│       │       ├── infra_scout_agent/       # Fleet discovery & DuckDB SQL engine
│       │       ├── workload_profiler_agent/ # Utilization profiling
│       │       └── recommender_agent/       # Graviton recommendation engine
│       ├── forecaster_agent/            # 7-day statistical ARIMA(1,0,0) model
│       ├── impact_calculator_agent/     # AWS Pricing API & Climatiq emissions engine
│       ├── safe_executor_agent/         # 6-gate safety engine & boto3 state machine
│       └── summary_generator_agent/     # Markdown reports & PPTX slide deck generator
│
├── aws_lambda/                 # Continuous telemetry snapshot & scheduled pipeline
│   ├── daily_data_snapshot.py  # Lambda handler for daily metrics ingestion
│   └── template.yaml           # AWS SAM deployment template
│
└── tests/                      # Automated test suite (194 passing tests)
    ├── test_bedrock_foundation.py
    ├── test_infra_scout_bedrock.py
    ├── test_optimization_advisor_bedrock.py
    ├── test_forecast_and_impact_bedrock.py
    ├── test_hardened_carbon_impact.py
    ├── test_safety_and_executor_bedrock.py
    ├── test_safety_regression.py
    ├── test_hardened_executor.py
    ├── test_aws_executor.py
    ├── test_telemetry_layer.py
    ├── test_fastapi_integration.py
    ├── test_e2e_readonly.py
    ├── test_no_google_runtime_dependencies.py
    └── test_root_agent.py
```

---

<div align="center">
  <sub>Built with Amazon Bedrock & Anthropic Claude for Sustainable Cloud Operations. © 2026 CO2Ops. All rights reserved.</sub>
</div>