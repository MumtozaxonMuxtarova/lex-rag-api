from datetime import date, datetime, timezone, timedelta
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Language = Literal['uz-Latn', 'uz-Cyrl', 'ru']

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Options(StrictModel):
    top_k: int = Field(default=5, ge=1, le=50)
    return_contexts: bool = True
    return_debug: bool = False
    temperature: Literal[0] = 0
    seed: int = 42
    as_of_date: date = Field(default_factory=lambda: datetime.now(timezone(timedelta(hours=5))).date())
    answer_language: Literal['auto', 'uz-Latn', 'uz-Cyrl', 'ru'] = 'auto'

class Item(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=2000)
    language: Language | None = None

    @field_validator('question', 'id')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('Value cannot be blank')
        return value

class Batch(StrictModel):
    run_id: str = Field(min_length=1, max_length=100)
    batch_id: str = Field(min_length=1, max_length=100)
    batch_index: int = Field(ge=1, le=10)
    total_batches: int = Field(ge=1, le=10)
    options: Options = Field(default_factory=Options)
    items: list[Item] = Field(min_length=1, max_length=10)

    @model_validator(mode='after')
    def check_batch(self):
        if len({item.id for item in self.items}) != len(self.items):
            raise ValueError('Duplicate question ID')
        if self.batch_index > self.total_batches:
            raise ValueError('batch_index exceeds total_batches')
        return self
