from pydantic import BaseModel, Field


class RenameNote(BaseModel):
    title: str = Field(min_length=1, max_length=200)
