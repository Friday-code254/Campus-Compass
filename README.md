# Campus Compass

**Campus Compass** is a small, local-first document assistant for campus guides and student handbooks. Upload a document, ask a question in plain language, and review the source passages used for the answer. If the uploaded documents do not provide enough evidence, the assistant abstains.

This project demonstrates a practical retrieval-augmented generation (RAG) workflow using familiar tools: FastAPI, SQLite, TF-IDF, and an optional OpenAI-compatible chat-completions API.

> The included Northstar Institute guides are fictional examples for the demo. They are not real campus policies.

## What it can do

- Upload PDF, TXT, and Markdown documents through the web interface.
- Extract text, split it into overlapping passages, and store searchable passages in SQLite.
- Rank passages with TF-IDF and cosine similarity, without a hosted vector database.
- Show source passages with each answer so users can check the evidence.
- Use an optional language model to write a concise answer with source labels such as [S1].
- Abstain when retrieval does not find enough evidence.
- Run a small, labeled evaluation for retrieval and abstention behavior.

## Try the demo

The sample documents live in data/sample_docs. Start the app, then upload the Markdown files through the Documents panel; the app does not add them automatically.

Example questions:

- What time does the main library close on weekdays?
- What attendance percentage is required for regular classes?
- How many counseling sessions are included each semester?
- What is the fine for parking in a reserved staff space? (The demo documents do not answer this, so the assistant should abstain.)

## Requirements

- Python 3.10 or newer
- pip
- An optional OpenAI-compatible chat-completions endpoint for generated answers

Without an LLM endpoint, the app still runs and shows the retrieved passages in preview mode.

## Run on Windows

Open PowerShell in the project folder and run:

~~~powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload
~~~

Then open http://127.0.0.1:8000. The interactive API documentation is at http://127.0.0.1:8000/docs.

If PowerShell blocks virtual-environment activation, run the commands without activating it:

~~~powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
~~~

## Run on macOS or Linux

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload
~~~

Open http://127.0.0.1:8000 in your browser.

## Configure answer generation (optional)

Campus Compass can use an OpenAI-compatible chat-completions service. In .env, set:

~~~dotenv
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=your-private-api-key
LLM_MODEL=your-model-name
~~~

The base URL should be the API base path; the app adds /chat/completions. Keep your key private and do not commit .env. The repository ignores that file.

When generation is configured, the app sends the question and retrieved passages to that endpoint. Use documents you are allowed to process with your chosen provider. Without these settings, no model call is made; the interface displays the passages for review instead.

## How it works

~~~mermaid
flowchart LR
    A[Upload document] --> B[Extract text]
    B --> C[Split into overlapping passages]
    C --> D[(SQLite)]

    E[Ask a question] --> F[TF-IDF ranking]
    D --> F
    F --> G{Evidence passes cutoffs?}
    G -- No --> H[Abstain]
    G -- Yes --> I[Show source passages]
    I --> J{LLM configured?}
    J -- No --> K[Retrieval preview]
    J -- Yes --> L[Concise answer with citations]
~~~

PDFs are processed with pypdf. Passages are 900 characters with a 120-character overlap. Retrieval scores are TF-IDF cosine similarities, not probabilities or confidence estimates. The default score cutoff is 0.12 and the query-term coverage cutoff is 0.35; both can be tuned in .env.

## Evaluate retrieval

Run the included evaluation from the project folder:

~~~powershell
python -m evals.run_eval
~~~

The script uses the fictional sample documents and 15 hand-written questions: 12 answerable and 3 deliberately unanswerable. The latest included evaluation reached 12/12 Recall@1, 12/12 answerable-question coverage, and 3/3 abstentions. This is a small demo set, not evidence of broad real-world accuracy. The evaluation measures retrieval behavior, not whether generated wording is correct. Its detailed report is written to evals/report.json and is excluded from the project archive.

## API routes

| Method | Route | Purpose |
| --- | --- | --- |
| GET | /api/health | Check that the service is running |
| GET | /api/documents | List uploaded documents |
| POST | /api/documents | Upload a PDF, TXT, or Markdown file |
| DELETE | /api/documents/{document_id} | Remove a document and its passages |
| POST | /api/chat | Ask a question and receive an answer plus sources |

## Project layout

~~~text
app/                 FastAPI app, ingestion, retrieval, storage, and LLM client
data/sample_docs/    Fictional campus documents for the demo
evals/dataset.json   Labeled retrieval questions
evals/run_eval.py    Retrieval evaluation script
static/              Browser UI, styles, and client-side chat logic
.env.example         Optional settings template
requirements.txt     Python dependencies
~~~

The local SQLite database is created at data/campus_compass.sqlite3 when the app starts. Uploaded document text and passage metadata are stored there; the original uploaded files are not retained by the app.

## Current limits

- Scanned PDFs are not OCR-processed; PDFs need selectable text.
- TF-IDF works best when the question and source use similar words. It may miss paraphrases.
- The optional model can still make mistakes. Review the cited passages for important decisions.
- The demo has no sign-in or per-user document separation. It is intended for local learning, not confidential records or official policy decisions.
- Uploads are limited to 10 MB by default. MAX_UPLOAD_MB in .env can raise this limit up to 25 MB.

## Design choices

- **TF-IDF and SQLite:** retrieval stays inexpensive and easy to inspect, with no vector database service to configure.
- **Citations and abstention:** answers include source labels, and weak matches are refused instead of being presented as supported facts.
- **Optional generation:** retrieval works on its own, which makes it possible to inspect the evidence path without an LLM key.
