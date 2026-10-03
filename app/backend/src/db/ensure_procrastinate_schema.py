"""Ensure the Procrastinate schema exists, without re-applying it.

``procrastinate schema --apply`` only works on an empty database (its own help
says so): it runs the full DDL unconditionally, with plain CREATE TYPE and no
version check. So every backend container recreate after the first deploy
crashed on ``type "procrastinate_job_status" already exists``. This module
applies the schema only when it is absent, making the entrypoint idempotent
across restarts and rebuilds.
"""

import psycopg
from procrastinate.schema import SchemaManager

from src.config import settings
from src.queue import app

TABLE = "procrastinate_jobs"


def main() -> None:
    with psycopg.connect(settings.sync_database_url) as conn:
        exists = conn.execute(
            "select 1 from information_schema.tables "
            "where table_schema = 'public' and table_name = %s",
            (TABLE,),
        ).fetchone()
    if exists:
        print("procrastinate schema already applied, skipping")
        return
    SchemaManager(app.connector).apply_schema()
    print("procrastinate schema applied")


if __name__ == "__main__":
    main()
