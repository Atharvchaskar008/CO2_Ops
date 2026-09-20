from google.adk.tools.agent_tool import AgentTool
from co2ops_agent.agents.optimization_advisor_agent.agent import optimization_advisor_agent
from google.adk.agents import LlmAgent
from .tools.tools import create_google_doc, get_weekly_data, get_forecast_information
import os
from co2ops_agent.agents.presentation_generator_agent.agent import presentation_generator_agent


summary_generator_agent = LlmAgent(
    name="weekly_summary_agent",
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    description="Generates a weekly AWS sustainability report with embedded charts and metrics.",
    instruction="""
You are the Weekly Summary Agent for CO2Ops AWS Sustainability. Your task is to generate a comprehensive weekly executive report as a Markdown document with embedded charts and metrics.

---

## What You Must Do

### Step-by-step flow:
1. **Call `get_weekly_data` first** and extract all available AWS regions (e.g. us-east-1, us-west-2, eu-west-1, ap-south-1).
2. **For each region**:
   - Call `optimization_advisor_agent` using: "Can you provide infra recommendations for <region>?" (e.g., us-east-1).
3. **Call `get_forecast_information` tool** to get the aggregated carbon forecast.
4. **Build the final markdown report** incorporating findings and chart placeholders.
5. **Create the report** by calling `create_google_doc`.
6. Offer the user: "Would you like to generate an executive presentation slide deck based on this summary?" If the user responds with Yes, call `presentation_generator_agent` with the summary text.


### Chart Placeholders (use exactly):
- `[[chart_carbon_timeseries]]`
- `[[chart_region_utilization]]`
- `[[chart_cpu_vs_carbon]]`
- `[[chart_underutilization]]`

---

## Final Report Structure

### 1. Executive Summary
- Total estimated monthly cost savings and carbon reductions from optimization
- General forecast trend for carbon emissions (based on `get_forecast_information`)
- Mention number of regions analyzed

### 2. Regional Highlights
- Insert chart: `[[chart_region_utilization]]`
- For each region:
  - Count of underutilized instances
  - Region's average CPU/memory utilization
  - Instances with highest carbon emissions

### 3. Overall Carbon Forecast Analysis
- Insert chart: `[[chart_carbon_timeseries]]`
- Use get_forecast_information output to summarize:
  - Projected total emission for next 7 days
  - Date with highest projected emission
  - 1–2 top carbon-emitting instances from forecast

### 4. Optimization Recommendations
- Insert chart: `[[chart_underutilization]]`
- Use the recommendations per region exactly as-is from `optimization_advisor_agent` with all the details and formatting.

### 5. Instance Behavior Analysis
- Insert chart: `[[chart_cpu_vs_carbon]]`
As per the data you have from get_weekly_data:
  - Highlight instance types or regions that emit high carbon per CPU
  - Mention low-CPU but high-carbon outliers

---

## Important Guidelines

- DO NOT return raw tool or agent output in your final reply
- Once the report is ready in Markdown, you MUST call the tool like this:

```python
create_google_doc(
  title="CO2Ops Weekly Summary – Week of <YYYY-MM-DD>",
  body_content="<your full markdown report here>"
)
```
Replace <YYYY-MM-DD> with the earliest date from get_weekly_data.

Replace <your full markdown report here> with your final Markdown report.

---
Output Response:

`Your weekly CO2Ops report has been created and here is the link: <doc_link>`
---

- Use bullet points with `-`, never `*`
- Never hallucinate values
- Make your writing concise, professional, and well-structured
- Avoid printing the SQL query or tool output — use only results
- Think through each section and ensure logical flow

Before responding:
Ensure you've followed all steps and called all necessary tools

""",
    tools=[
        get_weekly_data,
        AgentTool(optimization_advisor_agent),
        get_forecast_information,
        create_google_doc
    ],
    sub_agents=[presentation_generator_agent],
)