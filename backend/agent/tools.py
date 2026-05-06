"""Tool definitions for the LLM (OpenAI-compatible function-calling format, as used by Grok)."""
from __future__ import annotations

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_listings",
            "description": (
                "Search property listings from the database using structured filters. "
                "Call this tool only when you have at minimum: city, max_price, and listing_type. "
                "All other parameters are optional."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city":          {"type": "string",  "description": "City or area name exactly as stated by user"},
                    "listing_type":  {"type": "string",  "enum": ["rent", "buy"]},
                    "min_price":     {"type": "integer", "description": "Minimum price in USD/month or total"},
                    "max_price":     {"type": "integer", "description": "Maximum price in USD/month or total"},
                    "bedrooms":      {"type": "integer", "description": "Number of bedrooms"},
                    "property_type": {
                        "type": "string",
                        "enum": ["apartment", "house", "studio", "villa", "penthouse", "townhouse"],
                    },
                    "must_have_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags from approved vocabulary that the user stated as essential",
                    },
                    "nice_to_have_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags from approved vocabulary that the user mentioned but not essential",
                    },
                    "description_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Free-text phrases that did not map to any known tag, for full-text search",
                    },
                },
                "required": ["city", "listing_type", "max_price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_listing_detail",
            "description": "Get full details of a specific listing by its UUID. Call when user asks for more info about a specific property.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listing_id": {"type": "string", "description": "UUID of the listing"}
                },
                "required": ["listing_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_listings",
            "description": "Compare two or more listings side by side. Call when user asks to compare properties.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listing_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of listing UUIDs to compare",
                        "minItems": 2,
                        "maxItems": 4,
                    }
                },
                "required": ["listing_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_search",
            "description": "Save the current search filters for the user so they can be notified of new matching listings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name":    {"type": "string",  "description": "User-friendly name for this saved search"},
                    "filters": {"type": "object",  "description": "The current filter state to save"},
                    "notify":  {"type": "boolean", "description": "Whether to send alerts for new matches"},
                },
                "required": ["name", "filters"],
            },
        },
    },
]
