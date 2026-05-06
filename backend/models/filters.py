"""Pydantic model for extracted search filters."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class FilterState(BaseModel):
    city: Optional[str] = None
    listing_type: Optional[str] = None  # "rent" or "buy"
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    bedrooms: Optional[int] = None
    property_type: Optional[str] = None
    must_have_tags: list[str] = Field(default_factory=list)
    nice_to_have_tags: list[str] = Field(default_factory=list)
    description_keywords: list[str] = Field(default_factory=list)
