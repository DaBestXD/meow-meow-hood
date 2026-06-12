# Project Instructions

This is a Robinhood API Python package using `src/robinhood`.

- Use Python 3.11+.
- Prefer `uv` for commands.
- Keep line length at 80 characters
- If string literal cannot fit within 80 characters use # noqa: E501.
- Use Ruff formatting and Pyright typing.
- Avoid real Robinhood API calls in tests unless explicitly requested.
- Do not edit any code under src/ unless user says to do so.
- Before finishing code changes run:
  - `uv run scripts/fixy.py`

## Converting JSON payloads into python dataclasses

```bash
uv run /scripts/dataclass_construstor.py \
-d /src/robinhood/dataclasses/api_dataclasses.py \
-t "{json_text}"

```

## For general code reviews

- Run `uv run -m scripts.implementation_checker`
- Run `uv run scripts/fixy.py`

## For review before publishing

- Ensure version is bumped
- Run `uv run -m scripts.implementation_checker`
