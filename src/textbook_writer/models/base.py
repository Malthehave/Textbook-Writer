"""Shared pydantic base — no schema versioning or ID ceremony."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# OpenAI structured outputs reject format=uri from HttpUrl; use a plain pattern.
HttpsUrl = Annotated[str, Field(pattern=r"^https://[^\s]+$")]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")
