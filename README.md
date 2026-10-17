# Code Agent

A small command-line coding agent built with the OpenHands SDK. The first
workflow is deliberately focused: inspect the repository, propose a plan, wait
for approval, edit files, and run relevant checks.

## Requirements

- Python 3.12 or newer
- An LLM API key for a model supported by the OpenHands SDK

## Install

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item .env.example .env
```

Set `LLM_API_KEY` in `.env`. `LLM_MODEL` defaults to `gpt-5.5`; set
`LLM_BASE_URL` when using an OpenAI-compatible endpoint. `.env` is ignored by
Git. The app stores OpenHands conversation data in `data/conversations/` by
default; that directory is also ignored.

## Run

```powershell
code-agent --workspace C:\path\to\repository "Add input validation to the upload endpoint"
```

You can also run from this checkout with `python -m code_agent.main ...` after
installing the package. The agent presents a plan and waits for approval before
it can edit. Actions classified as medium or high risk require separate
approval. The agent does not commit or push. Its process exit code is `0` only
when it reports that all applicable checks passed.

## Project layout

- `src/code_agent/` contains the packaged CLI and the modules used by the first
  workflow.
- `examples/` contains the earlier, standalone OpenHands SDK reference scripts.
- `tests/` contains focused tests for workflow status handling.
- `data/` is reserved for local application state and is excluded from Git.

Planning, memory backends, retrieval, and additional providers can be added as
separate modules when a later workflow needs them.
