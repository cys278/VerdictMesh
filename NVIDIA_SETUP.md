# VerdictMesh demos with one NVIDIA API key

The core `src/verdictmesh` engine is model-agnostic. This patch adapts the cookbook examples to use the OpenAI-compatible NVIDIA endpoint and `z-ai/glm-5.3-flash`. The original Anthropic demo filenames remain for compatibility, but their model calls now use NVIDIA. The micro-SaaS example becomes NVIDIA-only rather than an Ollama/OpenAI hybrid.

## Install and run

From the repository root, activate your existing `.venv`, then run:

```bash
python -m pip install -e . openai python-dotenv
PYTHONPATH="$PWD/src" python -c "import verdictmesh; print(verdictmesh.__version__)"
```

Export your **new, unshared** key in the terminal; never put it in Python source:

```bash
export NVIDIA_API_KEY="your-replacement-key"
```

The previous key shared in chat/screenshot should be revoked. The free prototype endpoint may have limits or delays. Demos 01, 06 and 08 contain medical, compliance, or incident samples: only send data that you are authorized to upload to NVIDIA.

### Document Audit web interface (05)

```bash
python -m pip install fastapi uvicorn python-multipart PyMuPDF
PYTHONPATH="$PWD/src" python -m uvicorn main:app --app-dir cookbook/05-document-analysis/backend --reload
```

Open http://127.0.0.1:8000/frontend/index.html and use a non-confidential PDF. Press Ctrl+C to stop the server. The original backend requirements pinned VerdictMesh 0.4.0; this patch removes that pin so the editable local 0.7.0 package remains installed.

### Medical web interface (01)

Stop the Document Audit server first. From the repository root, install web dependencies and verify the editable package:

```bash
python -m pip install fastapi uvicorn python-multipart
PYTHONPATH="$PWD/src" python -c "import verdictmesh; print(verdictmesh.__version__)"
cd cookbook/01-ai-agents-for-medical-diagnostics/Webapp
python -m uvicorn main:app --reload
```

Open http://127.0.0.1:8000/static/index.html. Return to the repository root afterward with `cd ../../..`.

### Command-line demos

Run from the repository root, for example:

```bash
PYTHONPATH="$PWD/src" python cookbook/03-conflict-analysis/run_demo.py
PYTHONPATH="$PWD/src" python cookbook/02-micro-saas-validator/run_demo.py
PYTHONPATH="$PWD/src" python cookbook/04-supply-chain-replanning/run_demo.py
PYTHONPATH="$PWD/src" python cookbook/07-weighted-due-diligence/run_demo.py
PYTHONPATH="$PWD/src" python cookbook/06-ai-feature-compliance-gate-anthropic/run_demo.py
PYTHONPATH="$PWD/src" python cookbook/08-security-incident-triage-anthropic/run_demo.py
```

For any optional package missing, install its cookbook requirements after `pip install -e .`. Do not run `pip install verdictmesh` in these demos; that may replace your editable copy. The two Anthropic-named directories are retained but now call NVIDIA. Demo 03 is already adapted in your uploaded repository and is not overwritten by this patch.

## Verification limits

Python files were syntax-checked. Demo 03 has already completed successfully on your machine. The other hosted demos require live requests from your Mac and are not verified end-to-end here; different model outputs can also fail the original demos' strict JSON schemas. The free API key can be rate-limited; if you see a 429 or timeout, stop and inspect the exact error before retrying.
