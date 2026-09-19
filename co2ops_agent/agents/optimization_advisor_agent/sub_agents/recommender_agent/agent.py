from co2ops_agent.bedrock.agent import BedrockAgent
from co2ops_agent.bedrock.state import CO2OpsState

infra_recommender_agent = BedrockAgent(
    name="infra_recommender",
    description="Providing well crafted professional recommendations",
    system_instruction="""
    Your main goal is delivering final recommendations based on the found analysis: 
    
    Analysis:
    {analysis_results}
    
    Final output format:
    # Infrastructure Recommendations for [Region]
    ## Summary
    - [Short summary about what was found]
    
    ## Detailed Recommendations:
    - [Instance ID]
    - [Issue Identified]
    - [Current Instance Type]
    - [Recommmendation also mentioning which instance type to replace with]
    - [Potential savings based on current and target instance]
    -----------------------------------

    Format the recommendations in a professional format separated by horizontal bars.

    """,
    input_state_key="analysis_results",
    output_state_key="final_recommendations"
)