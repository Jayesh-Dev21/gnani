"""Worker entrypoint.

Runs the same image as the API. The only difference is that it drains the
transcription queue instead of serving HTTP, so transcription survives the API
being restarted without an ASR request ever occupying a request handler.
"""

import asyncio
import logging

from src.config import settings
from src.modules.transcription.recovery import recover_on_startup

# Imported for the side effect: this is what registers the tasks with the queue.
# Without it the worker starts cleanly and then fails every job.
from src.modules.summarisation import tasks as _summarisation_tasks  # noqa: F401
from src.modules.transcription import tasks as _transcription_tasks  # noqa: F401
from src.queue import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


async def main() -> None:
    logging.getLogger("worker").info("starting worker on queues: %s", settings.worker_queues)

    # Recovery defers jobs of its own, so the queue must be open before it runs.
    await app.open_async()
    await recover_on_startup()
    await app.run_worker_async(queues=[queue.strip() for queue in settings.worker_queues.split(",") if queue.strip()])


if __name__ == "__main__":
    asyncio.run(main())