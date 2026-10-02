"""The job queue.

Procrastinate on the same Postgres the notes live in, so deferring a job is an
insert and there is no second stateful service to operate. The connector is
psycopg3, which is why the settings expose a driver-free database URL.
"""

import procrastinate

from src.config import settings

app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(conninfo=settings.sync_database_url),
)

QUEUE_TRANSCRIPTION = "transcription"


async def defer_transcription(note_id: str, user_id: str) -> None:
    """Hand a note to the transcription queue.

    Called after the note row has committed. A crash between the commit and this
    insert leaves a queued note with no job, which the startup sweep repairs.
    """
    from src.modules.transcription.tasks import transcribe_note

    await transcribe_note.defer_async(note_id=note_id, user_id=user_id)