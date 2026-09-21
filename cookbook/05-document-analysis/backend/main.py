# backend/main.py
import os
import json
import asyncio
import uuid
from fastapi import HTTPException
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Import directly from the verdictmesh package
from verdictmesh.base import Agent
from verdictmesh.engine import Engine
from verdictmesh.aggregators import ConflictChecker

from utils.document_parser import parse_pdf_to_sentences
from prompts import FINANCE_PROMPT, LEGAL_PROMPT, OPS_PROMPT, LEASE_DUE_DILIGENCE_GOAL

app = FastAPI(title="VerdictMesh Parallel Reasoning Demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SERVE FRONTEND STATIC FILES ---
base_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(base_dir, "..", "frontend")
app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")


document_sessions = {}

# NVIDIA's hosted chat endpoint uses the OpenAI-compatible SDK.
api_key = os.getenv("NVIDIA_API_KEY")
if not api_key:
    raise RuntimeError("Set NVIDIA_API_KEY before starting the Document Audit server.")
nvidia_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=api_key,
    timeout=180.0,
    max_retries=0,
)
MODEL = "z-ai/glm-5.3-flash"

def call_nvidia(prompt: str, system=None) -> str:
    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": prompt})
    response = nvidia_client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.1,
        reasoning_effort="low",
        max_tokens=2048,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError(
            f"NVIDIA returned no answer (finish_reason={response.choices[0].finish_reason})."
        )
    return content

# --- LLM CALLABLES ---

def call_nvidia_aggregator(prompt: str) -> str:
    """Get the final cross-domain conflict report."""
    return call_nvidia(
        prompt,
        system="You are the Chief Justice. Output only a valid JSON conflict audit.",
    )

def call_nvidia_agent(prompt: str) -> str:
    """Get one isolated specialist report."""
    return call_nvidia(prompt)


# --- AGENT WRAPPERS ---
def parse_agent_response(raw_result, agent_name, color):
    if isinstance(raw_result, str):
        try:
            clean_str = raw_result.strip().removeprefix("```json").removesuffix("```").strip()
            parsed_result = json.loads(clean_str)
        except json.JSONDecodeError:
            parsed_result = {"selected_sentence_ids": [], "insight": "Failed to extract structured data."}
    else:
        parsed_result = raw_result

    return {
        "agent": agent_name,
        "color": color,
        "selected_sentence_ids": parsed_result.get("selected_sentence_ids", []),
        "insight": parsed_result.get("insight", "")
    }

class ExpertAgent(Agent):
    """Refactored agent class utilizing the Bring-Your-Own-LLM callable pattern."""
    def __init__(self, role: str, goal: str, color: str, system_prompt: str, llm_callable):
        super().__init__(role=role, goal=goal)
        self.color = color
        self.system_prompt = system_prompt
        self.llm_callable = llm_callable

    def execute(self, problem_data: str):
        # Construct the isolated prompt for the specialist
        prompt = f"{self.system_prompt}\n\nAnalyze the following data:\n{problem_data}"

        # Execute via the standard callable
        return self.llm_callable(prompt)


# --- API ROUTES ---
@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    file_bytes = await file.read(10 * 1024 * 1024 + 1)
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF must be under 10 MB.")
    if not file_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Upload a PDF file.")

    try:
        sentence_objects = parse_pdf_to_sentences(file_bytes)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read this PDF.")

    document_id = uuid.uuid4().hex
    document_sessions[document_id] = sentence_objects
    return {
        "status": "success",
        "document_id": document_id,
        "sentences": sentence_objects,
    }
    
async def run_verdictmesh_stream(document_context):
    global current_document_context
    yield f"data: {json.dumps({'status': 'engine_started', 'message': 'Booting thread-isolated experts via NVIDIA...'})}\n\n"

    # 1. Initialize Agents with the NVIDIA callable
    finance = ExpertAgent(
        role="Finance Agent",
        goal="Identify financial risks and liabilities.",
        color="#FFD54D",
        system_prompt=FINANCE_PROMPT,
        llm_callable=call_nvidia_agent
    )
    legal = ExpertAgent(
        role="Legal Agent",
        goal="Identify legal traps and governance limitations.",
        color="#00BEBE",
        system_prompt=LEGAL_PROMPT,
        llm_callable=call_nvidia_agent
    )
    ops = ExpertAgent(
        role="Operations Agent",
        goal="Identify operational bottlenecks and maintenance burdens.",
        color="#00A15E",
        system_prompt=OPS_PROMPT,
        llm_callable=call_nvidia_agent
    )

    agents = [finance, legal, ops]
    agent_color_map = {agent.role: agent.color for agent in agents}

    # 2. Instantiate the Native Aggregator
    boss = ConflictChecker(
        llm_callable=call_nvidia_aggregator,
        pairwise_audit=False,  # One audit request; avoids three slow pairwise requests.
        custom_goal=LEASE_DUE_DILIGENCE_GOAL,
        max_threads=3,
        show_log=True
    )

    # 3. Mount everything directly to the Engine
    engine = Engine(agents=agents, aggregator=boss, require_all_agents=True)

    # 4. Fire the complete execution pipeline
    document_payload = json.dumps(current_document_context)

    loop = asyncio.get_running_loop()
    execution_results = await loop.run_in_executor(None, engine.run, document_payload, True)

    # 5. Extract results out of the Report traces to stream cleanly to the UI
    for trace in execution_results.traces:
        color = agent_color_map.get(trace.agent_role, "#FFFFFF")

        # Determine the raw output based on the trace state
        raw_output = trace.output if trace.status == "success" else {"insight": f"Error: {trace.error_message}"}
        formatted_report = parse_agent_response(raw_output, trace.agent_role, color)

        yield f"data: {json.dumps({'status': 'agent_report', 'data': formatted_report})}\n\n"
        await asyncio.sleep(0.3)

    # 6. Pull the final aggregated output from the engine state
    yield f"data: {json.dumps({'status': 'aggregator_started', 'message': 'Compiling cross-domain conflict analysis...'})}\n\n"
    await asyncio.sleep(0.2)

    aggregated_report = execution_results.consensus
    if aggregated_report.summary == "Fatal execution error in the aggregator.":
        raise RuntimeError("The conflict audit failed; check the server log.")

    # Handle object conversion if the aggregator returned a structured Pydantic object
    if hasattr(aggregated_report, 'model_dump'):
        aggregated_report = aggregated_report.model_dump()
    elif isinstance(aggregated_report, str):
        try:
            aggregated_report = json.loads(aggregated_report)
        except json.JSONDecodeError:
            pass

    yield f"data: {json.dumps({'status': 'conflict_report', 'data': aggregated_report})}\n\n"
    yield f"data: {json.dumps({'status': 'complete'})}\n\n"


@app.get("/api/analyze")
async def analyze_document(document_id: str):
    document_context = document_sessions.pop(document_id, None)
    if document_context is None:
        raise HTTPException(status_code=404, detail="Upload a document first.")

    async def safe_stream():
        try:
            async for event in run_verdictmesh_stream(document_context):
                yield event
        except Exception as exc:
            yield f"data: {json.dumps({'status': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(safe_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
