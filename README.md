# task_agent

A personal AI agent that actually does things — reads your email, manages your calendar, and chats with you over a FastAPI endpoint. Built on LangGraph with a plugin architecture so you can bolt on new capabilities without touching the core.

```
you: "what's on my calendar tomorrow?"
agent: *actually checks your calendar*
you: "summarize my unread emails"
agent: *actually reads your gmail*
```

## Architecture

```
src/
├── core/           # The brain
│   ├── graph.py    # LangGraph agent loop
│   ├── llm.py      # Multi-provider LLM (Anthropic, OpenAI, DeepSeek, Qwen)
│   ├── plugin.py   # Plugin base class + registry
│   ├── api.py      # FastAPI server
│   ├── memory.py   # Checkpointed conversation memory
│   └── config.py   # Env-driven config, per-agent isolation
├── plugins/
│   ├── calendar/   # CalDAV (Google Calendar, iCloud)
│   └── gmail/      # Gmail via Google API
└── agents/         # Agent definitions (e.g. personal/)
```

Plugins register tools via a decorator, the graph wires them in automatically. Adding a plugin = subclass `Plugin`, implement `tools()`, done.

## Quick Start

```bash
cp .env.dev.personal .env
# fill in your API keys and credentials

pip install -r requirements.txt
python -m src.core.api     # or however you launch it
```

## Multi-Agent Support

Each agent gets its own env file, data directory, and credentials. Run a `personal` agent and a `business` agent side by side — fully isolated state, separate LLM configs, different plugin sets.

## Deployment

```bash
./deploy.sh   # Docker → Raspberry Pi
```

## Stack

LangGraph · LangChain · FastAPI · SQLite · Qdrant · CalDAV · Gmail API

## Dev

```bash
pip install -r requirements-dev.txt
ruff check src/ tests/
pytest --tb=short -q
```

---

*Built to run on a Raspberry Pi in a closet, because that's where the best infrastructure lives.*
