# applykit

Local-first job-application assistant: a FastAPI + SQLite backend under `app/`
with a React/Vite frontend under `frontend/`. It manages resumes, parses and
renders them, and discovers job postings from public job-board APIs.

## Development

`./dev.sh` boots the database migrations, uvicorn on
`http://127.0.0.1:8000` and the Vite dev server. `uv run pytest` runs the test
suite.

## Job sources — terms and privacy

This repository ships no `SourceAdapter` implementation. Job discovery requires
installing a package that registers an `applykit.sources` entry point; without
one, a discovery run fails with a clear configuration error. Public tests
exercise the seam through fakes.
