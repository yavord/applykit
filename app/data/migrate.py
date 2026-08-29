"""CLI: apply migrations to the resolved data root. Idempotent."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.data.db import run_migrations
from app.paths import data_root


def main() -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    head = ScriptDirectory.from_config(config).get_current_head()

    print(f"data root: {data_root()}")
    run_migrations()
    print(f"alembic head: {head}")


if __name__ == "__main__":
    main()
