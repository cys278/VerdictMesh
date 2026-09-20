import os
from pydantic import BaseModel, Field
from verdictmesh.base import Aggregator
from verdictmesh.engine import Engine
from verdictmesh.agents.presets import cto_agent, cmo_agent, cpo_agent, cfo_agent
from verdictmesh.nvidia import generate

call_nvidia = generate

# =====================================================================
# 1. Define Strict Output Schemas (The Evidence Gates)
# =====================================================================

class TechEval(BaseModel):
    feasibility_score: int = Field(ge=1, le=10, description="Technical feasibility score.")
    recommended_stack: str = Field(description="The most efficient technology stack.")
    biggest_hurdle: str = Field(description="The single biggest technical hurdle.")

class MarketingEval(BaseModel):
    target_audience: str = Field(description="Specific target audience persona.")
    primary_hook: str = Field(description="The primary marketing hook.")
    acquisition_channels: list[str] = Field(description="Top 2 cheap user acquisition channels.")

class ProductEval(BaseModel):
    why_it_will_fail: str = Field(description="Be brutal. Why will this fail?")
    hidden_competitors: list[str] = Field(description="Direct or indirect competitors.")
    churn_risk_factors: list[str] = Field(description="Why users will churn after week 1.")

class FinanceEval(BaseModel):
    pricing_model: str = Field(description="The best monetization strategy.")
    suggested_price: str = Field(description="Specific suggested price points.")
    justification: str = Field(description="How to justify the price to early adopters.")

# =====================================================================
# 2. Define the Aggregator
# =====================================================================

class VentureCapitalist(Aggregator):
    def __init__(self):
        super().__init__(
            role="Venture Capitalist", 
            goal="Decide if the idea is worth building based on the structured expert reports.",
            llm_callable=call_nvidia
        )

    def execute(self, agent_reports: dict) -> str:
        print(f"\n[{self.role}] Synthesizing reports and making final decision via NVIDIA...\n")
        
        # Use the built-in formatter from the parent class
        compiled_reports = self._format_reports(agent_reports)

        prompt = f"""You are a {self.role}. Your goal is to {self.goal}.
        
        EXPERT REPORTS (JSON Formatted Data):
        {compiled_reports}
        
        Based on the structured data above, provide a final executive summary including:
        1. GO / NO-GO Decision.
        2. The strongest reason FOR building it.
        3. The strongest reason AGAINST building it.
        4. Final pivot or adjustment recommendation to make it succeed.
        """
        
        return self.llm_callable(prompt)

# =====================================================================
# 3. Run the Engine
# =====================================================================

if __name__ == "__main__":
    # The Micro-SaaS Idea Input
    idea_input = "An app that uses AI to remind you to water your plants based on local weather, humidity in the house, and the specific breed of the plant."
    
    print(f"Evaluating Idea: '{idea_input}'\n")

    # Initialize Agents using Presets and Pydantic Formats
    micro_saas_desc = "Micro-SaaS idea description."
    
    agents = [
        cto_agent(llm_callable=call_nvidia, output_format=TechEval, input_description=micro_saas_desc),
        cmo_agent(llm_callable=call_nvidia, output_format=MarketingEval, input_description=micro_saas_desc),
        cpo_agent(llm_callable=call_nvidia, output_format=ProductEval, input_description=micro_saas_desc), # Still testing the local model here!
        cfo_agent(llm_callable=call_nvidia, output_format=FinanceEval, input_description=micro_saas_desc)
    ]

    # Initialize Aggregator
    aggregator = VentureCapitalist()

    # Create and run the VerdictMesh Engine
    engine = Engine(agents=agents, aggregator=aggregator)
    
    # Broadcast to all agents in parallel, then aggregate
    report = engine.run(problem_data=idea_input, show_log=True)

    
    # --- Create Results Directory ---
    output_dir = "cookbook/02-micro-saas-validator/results"
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n📁 Saving reports to '{output_dir}/' directory...\n")

    for trace in report.traces:
        # Extract role and output safely
        role = getattr(trace, 'agent_role', getattr(trace, 'agent_name', 'Specialist'))
        output = getattr(trace, 'output', getattr(trace, 'result', str(trace)))
        
        # Save individual trace to a file
        safe_filename = role.replace(" ", "_").replace("/", "").lower()
        file_path = os.path.join(output_dir, f"{safe_filename}_report.txt")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"ROLE: {role}\n")
            f.write("="*30 + "\n")
            f.write(output)
            
    # --- Print and Save the Final Aggregated Consensus ---
    final_verdict = report.consensus

    # Save the final verdict to a file
    final_file_path = os.path.join(output_dir, "final_venture_capitalist_verdict.txt")
    with open(final_file_path, "w", encoding="utf-8") as f:
        f.write("🚀 FINAL VENTURE CAPITALIST VERDICT\n")
        f.write("="*50 + "\n")
        f.write(str(final_verdict))
        
        print("🚀 FINAL VENTURE CAPITALIST VERDICT\n")
        print("="*50 + "\n")
        print(final_verdict)
        
    print(f"\n✅ All reports successfully saved in the '{output_dir}/' folder.")