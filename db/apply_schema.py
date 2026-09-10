"""Apply db/schema.sql to the database in DATABASE_URL.

Idempotent: the schema uses `create table if not exists`, so re-running is safe.

Run:  python -m db.apply_schema
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

SCHEMA = Path(__file__).resolve().parent / "schema.sql"


def main() -> None:
    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit(
            "DATABASE_URL not set. Copy .env.example to .env and paste your "
            "Supabase connection string (see README)."
        )

    engine = create_engine(url)
    sql = SCHEMA.read_text()
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)   # psycopg2 runs the whole multi-statement script

    # Report what now exists.
    with engine.connect() as conn:
        rows = conn.execute(text(
            "select table_name from information_schema.tables "
            "where table_schema = 'public' order by table_name"
        )).fetchall()
    print("schema applied. public tables:")
    for (name,) in rows:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
