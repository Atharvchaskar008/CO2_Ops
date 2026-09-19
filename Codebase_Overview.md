# CO2Ops - AWS Cloud Sustainability & FinOps Architecture

## What is CO2Ops?

**CO2Ops** is an autonomous multi-agent AI system designed to eliminate cloud waste and slash carbon emissions across **Amazon Web Services (AWS)** infrastructure.

By continuously auditing AWS EC2 instances, analyzing workload utilization patterns, forecasting resource demands with statistical time-series models, and executing safe, zero-downtime machine rightsizing, CO2Ops bridges the gap between FinOps (cost reduction) and GreenOps (carbon abatement).

Users interact with the system via an interactive **Live AWS Sustainability Console**, issuing high-level strategic directives such as:
> *"Audit underutilized EC2 instances in us-east-1 and propose rightsizing to AWS Graviton."*
> *"Forecast CPU and carbon emissions for i-01a2b3c4d5e6f7g80 over the next 7 days."*
> *"Execute safe migration of instance i-01a2b3c4d5e6f7g80 to m5.large."*
> *"Generate the weekly AWS executive sustainability report and presentation deck."*

---

## AWS Multi-Agent Architecture

The architecture is built on the **Google Agent Development Kit (ADK)** with specialized sub-agents tuned specifically for AWS infrastructure:

```
                          ┌───────────────────────────┐
                          │    Live AWS Console UI    │
                          │   (Frontend: Port 8501)   │
                          └─────────────┬─────────────┘
                                        │ REST / SSE
                          ┌─────────────▼─────────────┐
                          │   co2ops_agent (Root)     │
                          │  Gemini 2.0 Flash / ADK   │
                          └─────────────┬─────────────┘
         ┌──────────────────┬───────────┴───────────┬───────────────────┐
         ▼                  ▼                       ▼                   ▼
┌──────────────────┐ ┌────────────────┐ ┌────────────────────┐ ┌────────────────────┐
│optimization_     │ │forecasting_    │ │impact_calculator_  │ │safe_executor_agent │
│advisor_agent     │ │tool_agent      │ │agent               │ │                    │
│(EC2 Scout &      │ │(statsmodels    │ │(AWS Pricing API +  │ │(boto3 EC2 resize   │
│DuckDB Analytics) │ │ARIMA models)   │ │Climatiq AWS CO2)   │ │with auto-waiters)  │
└──────────────────┘ └────────────────┘ └────────────────────┘ └────────────────────┘
                                        │
                         ┌──────────────┴──────────────┐
                         ▼                             ▼
              ┌─────────────────────┐       ┌─────────────────────┐
              │summary_generator_   │       │presentation_        │
              │agent (DuckDB + S3)  │──────▶│generator_agent      │
              │                     │       │(python-pptx + S3)   │
              └─────────────────────┘       └─────────────────────┘
```

### 1. Root Orchestrator (`co2ops_agent/agent.py`)
- Master coordinator routing user requests to specialized sub-agents.
- Securely resolves credentials from environment variables, **AWS Secrets Manager**, or **AWS SSM Parameter Store** via `secrets_access_manager.py`.

### 2. Specialized Sub-Agents (`co2ops_agent/agents/`)
- **`optimization_advisor_agent`**:
  - `infra_scout_agent`: Performs in-memory SQL analytics using **DuckDB** over AWS server metrics and queries live EC2 instances via `boto3.client('ec2')`.
  - `workload_profiler_agent`: Evaluates CPU, memory, IOPS, and network thresholds. Translates underutilized x86 instances to modern rightsized instances or energy-efficient **AWS Graviton (m6g/c6g/t4g)** families.
  - `infra_recommender`: Packages findings into prioritised rightsizing recommendations.
- **`forecasting_tool_agent`**:
  - Pulls 14-day history from **Amazon CloudWatch** (with high-precision simulated fallback).
  - Fits dynamic **statsmodels ARIMA(1, 0, 0)** time-series models to forecast 7-day CPU utilization, memory, and carbon emissions.
- **`impact_calculator_agent`**:
  - Calculates real-time cost deltas querying the **AWS Pricing API** (`boto3.client('pricing')`) with a verified local EC2 on-demand price index fallback.
  - Calculates carbon footprint using the **Climatiq AWS Instance Batch API** (`/compute/v1/aws/instance/batch`) with regional carbon intensity models.
- **`safe_executor_agent`**:
  - Enforces safety gates: validates that 7-day forecasted CPU < 30% and Memory < 40% before allowing downsizing.
  - Automates EC2 rightsizing using `boto3`: stops instance $\to$ waits for stopped state $\to$ modifies `InstanceType` attribute $\to$ restarts instance $\to$ waits for running state.
- **`summary_generator_agent` & `presentation_generator_agent`**:
  - Computes fleet-wide weekly trends with DuckDB.
  - Renders 4 Matplotlib trend charts.
  - Generates executive Markdown reports and 16:9 `.pptx` presentations using `python-pptx`.
  - Stores all reports, charts, and decks in **Amazon S3** (`boto3.client('s3')`) with pre-signed download URLs.

### 3. Automated Data Pipeline (`/aws_lambda`)
- Replaces legacy GCP Cloud Functions and Cloud Scheduler.
- **`daily_data_snapshot.py`**: Serverless AWS Lambda function triggered by an **Amazon EventBridge** daily cron schedule. Aggregates daily EC2 metrics and stores snapshots in Amazon S3 for historical analytics.
- **`template.yaml`**: Complete AWS SAM (Serverless Application Model) infrastructure-as-code template for 1-click deployment.

### 4. Interactive Frontend (`/Frontend`)
- Responsive dark-mode sustainability dashboard featuring real-time fleet metrics, interactive chat drawer connected to the ADK backend, prompt chips, and executive downloads.
- Dockerized via lightweight, production-ready `nginx:alpine`.

---

## Testing & Quality Assurance

CO2Ops includes a comprehensive automated test suite in `tests/` covering every migrated AWS component:

```bash
# Run the entire test suite (46 tests)
python -m pytest tests/ -v
```

### Test Coverage Summary:
- **`test_aws_pricing.py`**: Validates AWS Pricing API client, rate normalization, and price index fallback.
- **`test_aws_carbon.py`**: Validates Climatiq AWS batch endpoint and regional grid carbon intensity model.
- **`test_aws_forecaster.py`**: Validates statsmodels ARIMA forecasting, NLP parsing, and CloudWatch integration.
- **`test_aws_executor.py`**: Validates safety gatekeeper and EC2 instance modification workflow.
- **`test_aws_scout.py`**: Validates DuckDB SQL execution, table registration, and query resilience.
- **`test_summary_and_presentation.py`**: Validates chart generation, Markdown report compilation, and Amazon S3 presigned URLs.
- **`test_secrets_access_manager.py`**: Validates AWS Secrets Manager and SSM Parameter Store fallbacks.
- **`test_root_agent.py`**: Validates root orchestrator and all sub-agent bindings.

---

## Deployment Architecture

CO2Ops is fully containerized and ready for deployment to AWS using:
- **AWS App Runner** or **Amazon ECS Fargate** for the Backend and Frontend containers.
- **Amazon S3** for metrics and reports storage.
- **AWS Lambda & Amazon EventBridge** for scheduled daily data pipelines.
- **Amazon ECR** for container image registry.
