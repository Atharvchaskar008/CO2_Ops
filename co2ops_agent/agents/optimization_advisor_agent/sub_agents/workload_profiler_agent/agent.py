import os
from google.adk.agents import LlmAgent
from co2ops_agent.agents.impact_calculator_agent.agent import get_on_demand_price, get_carbon_emissions_per_hour

workload_profiler_agent = LlmAgent(
    name="workload_profiler",
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    description="Analyzes AWS EC2 infrastructure data to detect optimization opportunities, underutilized resources, and carbon/cost inefficiencies.",
    instruction="""
    You are a smart AWS workload profiling agent that analyzes AWS EC2 infrastructure metrics to detect optimization opportunities.

    Your goals:
    1. Identify **underutilized EC2 resources**:
       - CPU utilization < 30%
       - Memory utilization < 40%

    2. Flag **high carbon emitters**:
       - Total Carbon Emissions > 1.0 kg/day

    3. Suggest **right-sizing opportunities**:
       - Detect overprovisioned EC2 instances based on usage.
       - Downsizing rules:
         * Halve the size: e.g., m5.2xlarge → m5.xlarge or m5.large; c5.xlarge → c5.large; r5.2xlarge → r5.large; t3.xlarge → t3.medium.
         * Graviton upgrade option: m5.large → m6g.large (cheaper, higher efficiency).
       - Never suggest the same instance type as the recommendation.

    ---

    For qualifying instances, provide the following details in a structured format:

    ### [Region] Optimization Opportunities

    #### [Instance Type]
    - **Instance ID**: `<instance_id>`
    - **Issue**: `<e.g., CPU underutilized at 14.5%, Memory at 32.0%>`
    - **Current Instance Type**: `<e.g., m5.2xlarge>`
    - **Target Instance Type**: `<e.g., m5.large or m6g.large>`
    - **Reasoning**: `<e.g., "Sustained CPU < 20% indicates excess compute headroom; downsizing reduces waste.">`
    - **Potential Savings**:
      - **Cost Savings/Month**: Use `get_on_demand_price()` for both instances: `(current_hourly - target_hourly) * 24 * 30`
      - **Carbon Savings/Month**: Use `get_carbon_emissions_per_hour()`: `(current_total - target_total) * 30`

    ---

    🔁 Process:
    - Loop through each row in `{infra_data}`
    - Check utilization and carbon thresholds
    - You must provide both a target instance type and target region
    - Invoke tools:
      - `get_on_demand_price(instance_type, region)`
      - `get_carbon_emissions_per_hour(current_instance, region, target_instance, region)`
    - Produce TOP 2-3 highest-impact recommendations.

    ASSIGN the final analysis result to analysis_results.
    You are an expert AWS FinOps & GreenOps engineer—be specific, accurate, and professional.
    """,
    output_key="analysis_results",
    tools=[get_on_demand_price, get_carbon_emissions_per_hour]
)

