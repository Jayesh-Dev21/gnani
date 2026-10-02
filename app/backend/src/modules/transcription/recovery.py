"""Startup recovery.

A crash can leave a note in a state no worker will ever finish: the note says
`transcribing` but the process holding it is gone, or the note is `queued` and
its job died before anyone claimed it. Both are repaired before the worker
accepts new jobs, so a fresh deployment never shows a note that is stuck.

A job only counts as live while the worker running it is still reporting a
heartbeat. Without that check a dead worker's in-flight job looks live forever.
A `doing` job with no worker attached is exactly that case: the worker died
holding it, so the note needs a fresh job.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select, text

from src.db.models import Note, NoteStatus
from src.db.session import session_factory
from src.queue import defer_transcription

log = logging.getLogger("transcription.recovery")

# Procrastinate refreshes a worker's heartbeat every 10 seconds. Two missed
# heartbeats plus slack is comfortably beyond that, so this only trips on a
# worker that is genuinely gone.
WORKER_STALE_AFTER_SECONDS = 90


async def recover_on_startup() -> None:
    stale = await _reset_expired_leases()
    orphans = await _find_notes_needing_a_job()
    await _requeue(stale | orphans)


async def _reset_expired_leases() -> set[str]:
    """Return notes whose lease has expired to queued, keeping provider_job_id.

    The audio was already sent to Gnani, so the job id survives deliberately: the
    next attempt resumes that job instead of paying for the same file twice.
    """
    now = datetime.now(UTC)
    async with session_factory() as session:
        notes = (
            await session.scalars(
                select(Note).where(
                    Note.status == NoteStatus.TRANSCRIBING,
                    Note.lease_expires_at.is_not(None),
                    Note.lease_expires_at <= now,
                )
            )
        ).all()

        for note in notes:
            note.status = NoteStatus.QUEUED
            note.attempt_id = None
            note.lease_expires_at = None
            note.updated_at = now

        await session.commit()
        reclaimed = {str(note.id): str(note.user_id) for note in notes}

    if reclaimed:
        log.info("reset %d abandoned transcription(s) to queued", len(reclaimed))
    return reclaimed


async def _find_notes_needing_a_job() -> dict[str, str]:
    """Queued notes whose job is missing or was abandoned by a dead worker."""
    async with session_factory() as session:
        rows = await session.execute(
            text(
                """
                SELECT n.id::text AS id, n.user_id::text AS user_id
                  FROM notes n
                 WHERE n.status = :queued
                   AND NOT EXISTS (
                         SELECT 1
                           FROM procrastinate_jobs j
                           LEFT JOIN procrastinate_workers w ON w.id = j.worker_id
                          WHERE j.args ->> 'note_id' = n.id::text
                            AND (
                                  j.status = 'todo'
                               OR (j.status = 'doing'
                                   AND j.worker_id IS NOT NULL
                                   AND w.last_heartbeat > now() - :stale_after * interval '1 second')
                            )
                   )
                """
            ),
            {
                "queued": NoteStatus.QUEUED.value.upper(),
                "stale_after": WORKER_STALE_AFTER_SECONDS,
            },
        )
        return {row["id"]: row["user_id"] for row in rows.mappings()}


async def _requeue(notes: dict[str, str]) -> None:
    for note_id, user_id in notes.items():
        log.info("requeueing note %s", note_id)
        await defer_transcription(note_id, user_id)

    if notes:
        log.info("requeued %d note(s)", len(notes))