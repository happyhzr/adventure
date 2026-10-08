# Backend setup

Run these commands from the `backend` directory:

```sh
cp .env_example .env
uv sync --frozen
uv run uvicorn backend.main:app --reload
```

Before starting the server, set `DEEPSEEK_API_KEY` in `.env` to a real key
from your DeepSeek account. If migrating an existing `.env`, replace
`OPENAI_API_KEY` with `DEEPSEEK_API_KEY`; OpenAI credentials cannot be reused.
Keep your credentials out of version control.

`DEEPSEEK_MODEL` defaults to `deepseek-flash` and can be changed to another
model available through your DeepSeek account. Story generation uses
`langchain-deepseek` and its official DeepSeek endpoint.
