"""Pydantic models for property listings."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class Listing(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    listing_type: str
    property_type: Optional[str] = None
    price: int
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    area_sqft: Optional[int] = None
    city: str
    neighbourhood: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    tags: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    available: bool = True
    agent_id: Optional[UUID] = None
    created_at: Optional[datetime] = None


class ListingSummary(BaseModel):
    """Lightweight listing model for list views."""

    id: UUID
    title: str
    listing_type: str
    price: int
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    city: str
    neighbourhood: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
