# LangGraph Module — DB MoveOptimizer

This module contains two LangGraph workflows that can be visualised and run interactively in **LangSmith Studio**.

- **`db_mover`** — simple single-node chat workflow (notebook 01)
- **`analyst_optimizer_pipeline`** — two-agent pipeline: Analyst → Optimizer with tool use (notebook 04)

---

## Prerequisites

Make sure you have the following installed on your machine before starting:

- **Python 3.11 or higher** — check with `python3 --version`
- **uv** (Python package manager) — install with:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
  Then restart your terminal and verify with `uv --version`.

---

## Step 1 — Get your University GPT API key

Every team member needs their own personal API key for the University GPT endpoint.

1. Go to [https://chat.kiconnect.nrw/](https://chat.kiconnect.nrw/) and log in with your university account.
2. Navigate to your profile / API settings and create a new API key.
3. Copy the key — you will need it in the next step.

---

## Step 2 — Create your `.env` file

In the `langgraph_module/` folder, create a file named exactly **`.env`** (note the leading dot, no file extension).

Paste the following into it and fill in your key:

```
UNI_GPT_API_KEY=your_university_gpt_key_here
```

If you also want to trace your runs in LangSmith, add the following lines too (all optional):

```
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your_langsmith_key_here
LANGSMITH_PROJECT="AIIM_mobility_advisor"
```

To get a LangSmith API key: go to [https://smith.langchain.com](https://smith.langchain.com), sign up for a free account, then go to **Settings → API Keys → Create API Key**. The key starts with `lsv2_pt_...` — copy it immediately, you cannot view it again.

Your complete `.env` file (with tracing enabled) looks like this:

```
UNI_GPT_API_KEY=your_university_gpt_key_here
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=lsv2_pt_your_key_here
LANGSMITH_PROJECT="AIIM_mobility_advisor"
```

Your `langgraph_module/` folder should now look like this:
```
langgraph_module/
├── .env                  ← you just created this
├── langgraph.json
├── langgraph_agent.py
├── pipeline_agent.py
├── pyproject.toml
└── uv.lock
```

> **Note:** `.env` files are listed in `.gitignore` — your keys will never be committed to the repository.

---

## Step 3 — Navigate to the module folder

Open a terminal and navigate into the `langgraph_module/` directory.

**Mac / Linux:**
```bash
cd langgraph_module
```

**Windows (Command Prompt or PowerShell):**
```
cd %USERPROFILE%\Documents\GitHub\AIIM_DB_mobility_advisior\langgraph_module
```

Adjust the path if your repo is in a different location.

---

## Step 4 — Install dependencies

Run the following command inside `langgraph_module/`:

```bash
uv sync
```

This reads `pyproject.toml` and installs all required packages (LangGraph, LangChain, OpenAI client, pandas, etc.) into a local `.venv` folder. It takes about 30–60 seconds the first time.

---

## Step 5 — Start the local server

Still inside `langgraph_module/`, run:

**Mac / Linux:**
```bash
.venv/bin/langgraph dev
```

**Windows:**
```
.venv\Scripts\langgraph dev
```

You should see output like this:

```
Starting LangGraph API server...
LangGraph Studio: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

**Keep this terminal open** — the server must stay running while you use Studio.

To stop the server at any time, press **Ctrl + C** in the terminal (Mac, Linux, and Windows).

---

## Step 6 — Open LangSmith Studio

> **Important: Safari is not supported.** Open the Studio link in **Chrome** or **Firefox**.

Copy the Studio URL printed in your terminal and open it in Chrome or Firefox:
```
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

You will see the LangSmith Studio interface with your workflows loaded.

---

## Step 7 — Select a workflow and run it

At the top of the Studio interface there is a dropdown to select which graph to run.

---

### Running `analyst_optimizer_pipeline`

This is the main two-agent pipeline. Select it from the dropdown — you will see three input fields: **travel_data**, **analyst_summary**, and **messages**.

- **`travel_data`**: Paste the JSON below.
- **`analyst_summary`**: Leave empty.
- **`messages`**: Leave as `[]`.

**Copy this into the `travel_data` field:**

```json
{
  "user_id": "USR-0042",
  "name": "Anna Müller",
  "current_subscriptions": ["BahnCard 25 (2nd class)"],
  "travel_log": [
    {"date": "2026-05-02", "origin": "Köln Hbf", "destination": "Frankfurt Hbf", "ticket_type": "Flexpreis", "price_eur": 89.00, "class": 2},
    {"date": "2026-05-09", "origin": "Frankfurt Hbf", "destination": "Köln Hbf", "ticket_type": "Sparpreis", "price_eur": 17.90, "class": 2},
    {"date": "2026-05-16", "origin": "Köln Hbf", "destination": "Frankfurt Hbf", "ticket_type": "Flexpreis", "price_eur": 89.00, "class": 2},
    {"date": "2026-05-23", "origin": "Frankfurt Hbf", "destination": "Düsseldorf Hbf", "ticket_type": "Deutschlandticket", "price_eur": 49.00, "class": 2},
    {"date": "2026-05-30", "origin": "Köln Hbf", "destination": "Frankfurt Hbf", "ticket_type": "Sparpreis", "price_eur": 24.90, "class": 2}
  ]
}
```

Click **Submit / Run**. The graph will step through:
1. `analyst` — reads the travel log and produces a structured summary
2. `optimizer` — receives the summary, calls the `lookup_subscriptions` tool, then returns a recommendation
3. `tools` — executes the tool call
4. `optimizer` (again) — produces the final recommendation

The final subscription recommendation appears in the last entry of the **messages** field.

---

### Running `db_mover`

This is the simpler single-node workflow. Select it from the dropdown — you will see three fields: **messages**, **response**, and **status**.

- **`response`** and **`status`**: Leave empty.
- **`messages`**: Paste the following.

**Copy this into the `messages` field:**

```json
[{"role": "user", "content": "What are the best mobility options from Cologne to Berlin?"}]
```

Click **Submit / Run**. The response from the University GPT appears in the **response** field.

---

## Viewing traces in LangSmith (optional)

If you added the LangSmith keys to your `.env`, every run is automatically traced. Go to [https://smith.langchain.com](https://smith.langchain.com) → **Projects** → **AIIM_mobility_advisor** to view the full execution history of every run, including each LLM call, tool call, and state transition.

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| Error: Missing credentials / OPENAI_API_KEY | `UNI_GPT_API_KEY` is not set | Check `.env` has `UNI_GPT_API_KEY=...` with no quotes or extra spaces |
| Studio does not load | Using Safari | Open the link in Chrome or Firefox |
| Studio shows "not connected" | Server is not running | Make sure the `langgraph dev` command is still running in a terminal |
| `uv sync` fails with "wrong directory" | You are in the wrong folder | Make sure you `cd` into `langgraph_module/` before running `uv sync` |
| `.env` file not found / keys not loading | File is named `.env.txt` or saved in the wrong folder | The file must be named exactly `.env` and be inside `langgraph_module/` |
