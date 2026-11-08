from pydantic import BaseModel, ConfigDict


class Cerrado(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)
