"""
Demo 08 — Security Incident Triage (NVIDIA)

Three security specialists analyse the same incident export in parallel, each in
complete isolation:

  * Security Threat Hunter      — external intrusion, IoCs, ATT&CK tactics
  * Insider Threat Analyst      — misuse by an authenticated user
  * Breach Notification Analyst — regulatory exposure (GDPR Art. 33/34)

A Synthesizer then merges their independent findings into a single incident
triage memo. The LLM is NVIDIA GLM, wired via an OpenAI-compatible client.

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
    breach_notification_analyst,
    insider_threat_analyst,
    security_threat_hunter,
)

def call_nvidia(prompt: str) -> str:
    return generate(prompt, max_tokens=3072)


if __name__ == "__main__":
    incident_path = os.path.join(os.path.dirname(__file__), "sample_input", "incident_log.txt")
    with open(incident_path, "r", encoding="utf-8") as f:
        incident = f.read()

    print(f"Triaging incident with {MODEL} across 3 isolated security specialists...\n")

    agents = [
        security_threat_hunter(llm_callable=call_nvidia),
        insider_threat_analyst(llm_callable=call_nvidia),
        breach_notification_analyst(llm_callable=call_nvidia),
    ]

    engine = Engine(
        agents=agents,
        aggregator=Synthesizer(llm_callable=call_nvidia, show_log=True),
    )

    report = engine.run(problem_data=incident, show_log=True)

    print("\n" + "=" * 60)
    print("INCIDENT TRIAGE MEMO")
    print("=" * 60)
    print(report.consensus.narrative)

    print("\nKey Takeaways:")
    for takeaway in report.consensus.key_takeaways:
        print(f"  - {takeaway}")

    print(f"\nConfidence: {report.consensus.confidence}")
