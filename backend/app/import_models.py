"""Bounded, selected source evidence; no marketing payloads or access tokens."""
from typing import Annotated, Literal
from uuid import UUID
from pydantic import Field, model_validator
from .schemas import Contract

SpecKey = Literal['name', 'configuration', 'cpu', 'os', 'ram', 'storage', 'weight', 'display', 'maxRam', 'batteryWh']

class SourceField(Contract):
    field: SpecKey
    feature_id: Annotated[str, Field(max_length=20)] = ''
    raw: Annotated[str, Field(max_length=500)]
    unit: Annotated[str, Field(max_length=40)] = ''
    normalized: Annotated[str, Field(max_length=300)]

class ImportEvidence(Contract):
    receipt_id: UUID
    provider: Literal['Open Icecat'] = 'Open Icecat'
    product_id: Annotated[str, Field(pattern=r'^\d{1,12}$')]
    brand: Annotated[str, Field(min_length=1, max_length=100)]
    mpn: Annotated[str, Field(min_length=1, max_length=200)]
    source_url: Annotated[str, Field(max_length=2000)]
    retrieved_at: Annotated[str, Field(max_length=40)]
    language: Literal['EN'] = 'EN'
    source_updated_at: None = None  # Not exposed by the selected API sections.
    mapper_version: Literal['1.0.0'] = '1.0.0'
    fields: Annotated[list[SourceField], Field(max_length=12)]
    issues: Annotated[list[Annotated[str, Field(max_length=300)]], Field(max_length=20)]

class ImportRequest(Contract):
    request_id: UUID
    mode: Literal['link', 'id', 'mpn']
    value: Annotated[str, Field(max_length=2000)] = ''
    brand: Annotated[str, Field(max_length=100)] = ''
    mpn: Annotated[str, Field(max_length=200)] = ''

    @model_validator(mode='after')
    def identifiers(self):
        if self.mode == 'mpn':
            if not self.brand.strip() or not self.mpn.strip():
                raise ValueError('Enter both the brand and the exact manufacturer part number.')
        elif not self.value.strip():
            raise ValueError('Enter an Icecat product link or product ID.')
        return self
