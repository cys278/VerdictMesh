import os
from pathlib import Path
from dotenv import load_dotenv

from pydantic import BaseModel, field_validator, ConfigDict

from verdictmesh.engine import Engine
from verdictmesh.aggregators import ConflictChecker
from verdictmesh.agents.presets import cfo_agent, cto_agent, cro_agent
from openai import OpenAI

# NVIDIA's free prototype endpoint uses the OpenAI-compatible Python client.
load_dotenv()
api_key = os.getenv("NVIDIA_API_KEY")
if not api_key:
    raise RuntimeError("Set NVIDIA_API_KEY in your terminal before running this demo.")

nvidia_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=api_key,
    timeout=180.0,
    max_retries=0,
)

def call_nvidia(prompt: str) -> str:
    """Send a specialist or audit prompt to NVIDIA's hosted text model."""
    response = nvidia_client.chat.completions.create(
        model="z-ai/glm-5.3-flash",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        reasoning_effort="low",
        max_tokens=2048,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError(
            f"Model returned no answer (finish_reason={response.choices[0].finish_reason})."
        )
    return content


# ==============================================================================
# 2. Define Output Schemas for Agents using pydantic
# ==============================================================================

class FinancialAssessment(BaseModel):
    valuation_verdict: str
    risk_level: str
    primary_concern: str
    
    # Silently discard any extra hallucinated keys from the LLM
    model_config = ConfigDict(extra='ignore')

class TechDueDiligence(BaseModel):
    architecture_viability: str
    estimated_refactor_timeline: str
    blockers: list[str]
    
    model_config = ConfigDict(extra='ignore')

    # Robust coercion to handle LLM hallucinations 
    @field_validator('blockers', mode='before')
    @classmethod
    def ensure_list_format(cls, v):
        if isinstance(v, str):
            return [v]
        elif isinstance(v, list):
            return [str(b) for b in v]
        return []

class RevenueProjection(BaseModel):
    q3_upsell_confidence: str
    expected_integration_speed: str
    scaling_rationale: str  # Added to give the Conflict Checker enough context
    
    model_config = ConfigDict(extra='ignore')


# ==============================================================================
# 3. Orchestration & Execution
# ==============================================================================

def main():
    print("Loading Confidential Target Dossier...")
    demo_dir = Path(__file__).resolve().parent
    input_path = demo_dir / "sample_input" / "target_dossier.txt"
    output_path = demo_dir / "results" / "output.txt"
    
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            dossier_data = f.read()
    except FileNotFoundError:
        print(f"Error: {input_path} not found.")
        return

    # Initialize the parallel workers using OFFICIAL PRESETS
    # We override input_description to inject the precise instruction rules from the original code
    agents = [
        cfo_agent(
            llm_callable=call_nvidia, 
            output_format=FinancialAssessment,
            input_description="Target Dossier. You MUST extract the exact runway timeline (e.g., months left) and specific cash burn numbers into your primary concern."
        ),
        cto_agent(
            llm_callable=call_nvidia, 
            output_format=TechDueDiligence,
            input_description="Target Dossier. Focus on infrastructure costs, tech debt, and key personnel risks."
        ),
        cro_agent(
            llm_callable=call_nvidia, 
            output_format=RevenueProjection,
            input_description="Target Dossier. You MUST extract the exact target metrics, client volume, and explicit timelines (e.g., Q3) for the cross-selling strategy and include them in your scaling rationale."
        )
    ]
    
    # define custom goal 
    ma_due_diligence_goal = (
        "Outcome: A structured executive audit identifying fatal M&A risks, valuation illusions, "
        "timeline paradoxes, and fundamentally incompatible strategies between the C-suite reports.\n"
        "Constraints: Do not flag omissions. A department head ignoring an out-of-domain metric is expected. "
        "Furthermore, if two executives agree on a risk (e.g., both acknowledge the founder leaving), this is alignment, NOT a conflict. Do not flag agreements.\n"
        "CRITICAL COUNTING RULE: You must consolidate conflicts by their core root cause. If a massive infrastructure cost "
        "simultaneously ruins the CRO's profit margins and invalidates the CFO's $12M valuation, combine this into a SINGLE "
        "comprehensive 'Valuation/Margin' conflict. Do not split symptoms into multiple bullet points.\n"
        "Evidence Required: A conflict exists ONLY if Expert A's hard timeline, financial runway, or technical debt makes Expert B's "
        "revenue projection or integration strategy mathematically impossible or financially disastrous.\n"
        "Final Answer: Return ONLY valid JSON matching the exact schema."
    )
    
    # Initialize the Aggregator
    boss = ConflictChecker(
        llm_callable=call_nvidia, 
        pairwise_audit=False,  # One model request for the initial audit
        custom_goal=ma_due_diligence_goal,
        max_threads= 3, # Optimized for 3 pairs (CFO/CTO, CFO/CRO, CTO/CRO)
        show_log=True
    )

    # Initialize the Framework Engine
    engine = Engine(agents=agents, aggregator=boss, require_all_agents=True)
    
    report = engine.run(problem_data=dossier_data, show_log=True)
    if report.consensus.summary == "Fatal execution error in the aggregator.":
        raise RuntimeError("Conflict audit failed; inspect the error above. No report was saved.")

    # ==============================================================================
    # 4. Format and Save the Output
    # ==============================================================================
    
    print("\n[Engine] Formatting results for output.txt...")
    output_lines = [
        "VerdictMesh: Executive Conflict Analysis Report\n",
        "="*60,
        " PHASE 1: ISOLATED EXPERT FINDINGS (STRUCTURED DATA)",
        "="*60
    ]

    # Append Phase 1: Structured JSON Outputs
    for trace in report.traces:
        output_lines.append(f"\n[{trace.agent_role}]")
        if trace.status == "success":
            # The output is now a parsed Pydantic object, so we dump it to JSON for saving
            output_lines.append(trace.output)
        else:
            output_lines.append(f"Error: {trace.error_message}")

    output_lines.extend([
        "\n" + "="*60,
        " PHASE 2: CONFLICT AUDIT (EXECUTIVE SUMMARY)",
        "="*60
    ])
    
    # Append Phase 2: Structured Audit 
    if report.consensus.has_conflicts:
        output_lines.append("\n🚨 CRITICAL MISALIGNMENTS DETECTED 🚨\n")
        for conflict in report.consensus.conflicts:
            output_lines.append(f"- Severity: {conflict.severity}")
            output_lines.append(f"  Involved: {', '.join(conflict.involved_agents)}")
            output_lines.append(f"  Description: {conflict.description}\n")
        
        output_lines.append(f"Executive Summary:\n{report.consensus.summary}\n")
    else:
        output_lines.append("\nAll executive perspectives are aligned. Clear to proceed.")

    # Ensure output directory exists before writing
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the compiled content to output.txt
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
        
    print(f"\n✅ Analysis complete. Results successfully saved to {output_path}")

if __name__ == "__main__":
    main()