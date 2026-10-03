from typing import Literal

from pydantic import BaseModel, Field


class RenameNote(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class RetryNote(BaseModel):
    """Which step to run again.

    Omitted, the step is inferred from the note's state. Sending it explicitly lets
    the user ask for one more transcript of the same audio, which appends a new
    iteration rather than replacing the ones already there.
    """

    target: Literal["transcription", "summary"] | None = None
