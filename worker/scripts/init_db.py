from pathlib import Path

from app.config import ROOT_DIR, Settings
from app.db import get_conn, init_schema


def main() -> None:
    settings = Settings.load()
    conn = get_conn(settings.db_path)
    schema_sql = (ROOT_DIR / "worker" / "sql" / "schema.sql").read_text(encoding="utf-8")
    init_schema(conn, schema_sql)
    conn.close()
    print(f"Initialized DB at {settings.db_path}")


if __name__ == "__main__":
    main()

