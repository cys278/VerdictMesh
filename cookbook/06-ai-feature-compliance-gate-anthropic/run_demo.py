"""
Demo 06 — AI Feature Launch Compliance Gate (NVIDIA)

Four regulatory specialists review the same feature dossier in parallel, each in
complete isolation, then a Synthesizer merges their findings into one go / no-go
compliance memo. The LLM is NVIDIA GLM, wired via an
OpenAI-compatible client.

Run:
    export NVIDIA_API_KEY="your-key"
    pip install -r requirements.txt
    python run_demo.py
"""
import os

from verdictmesh.nvidia import generate, MODEL

from verdictmesh.engine import Engine
from verdictmesh.aggregators import Synthesizer
from verdictmesh.agents.presets import (
    data_sovereignty_auditor,
    ai_risk_assessor,
    phi_sanitizer,
    licensing_reviewer,
)

def call_nvidia(prompt: str) -> str:
    return generate(prompt, max_tokens=3072)


if __name__ == "__main__":
    dossier_path = os.path.join(os.path.dirname(__file__), "sample_input", "feature_dossier.txt")
    with open(dossier_path, "r", encoding="utf-8") as f:
        feature_dossier = f.read()

    print(f"Reviewing feature dossier with {MODEL} across 4 isolated compliance specialists...\n")

    agents = [
        data_sovereignty_auditor(llm_callable=call_nvidia),
        ai_risk_assessor(llm_callable=call_nvidia),
        phi_sanitizer(llm_callable=call_nvidia),
        licensing_reviewer(llm_callable=call_nvidia),
    ]

    engine = Engine(
        agents=agents,
        aggregator=Synthesizer(llm_callable=call_nvidia, show_log=True),
    )

    report = engine.run(problem_data=feature_dossier, show_log=True)

    print("\n" + "=" * 60)
    print("FINAL COMPLIANCE MEMO")
    print("=" * 60)
    print(report.consensus.narrative)

    print("\nKey Takeaways:")
    for takeaway in report.consensus.key_takeaways:
        print(f"  - {takeaway}")

    print(f"\nConfidence: {report.consensus.confidence}")
