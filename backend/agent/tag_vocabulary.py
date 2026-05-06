"""Approved tag vocabulary. The LLM is instructed to use ONLY these tag slugs."""
from __future__ import annotations

VALID_TAGS: dict[str, list[str]] = {
    "kitchen": [
        "open_plan_kitchen", "galley_kitchen", "island_kitchen", "breakfast_bar",
        "butler_pantry", "updated_kitchen", "gourmet_kitchen",
    ],
    "interior_style": [
        "exposed_brick", "hardwood_floors", "high_ceilings", "vaulted_ceilings",
        "crown_moulding", "built_in_shelves", "fireplace", "bay_windows", "skylights",
        "original_features", "modern_finishes", "industrial_style", "scandinavian_style",
        "mid_century_modern", "minimalist",
    ],
    "outdoor": [
        "private_garden", "rooftop_terrace", "balcony", "patio", "deck",
        "communal_garden", "courtyard", "pool", "hot_tub", "outdoor_kitchen", "front_garden",
    ],
    "parking": [
        "garage", "double_garage", "off_street_parking", "allocated_parking",
        "driveway", "on_street_parking", "electric_vehicle_charger",
    ],
    "building_amenities": [
        "concierge", "gym", "swimming_pool", "communal_roof_terrace", "bike_storage",
        "parcel_room", "lift", "wheelchair_accessible", "smart_home", "video_intercom",
    ],
    "location_type": [
        "city_centre", "suburban", "rural", "waterfront", "beachfront",
        "mountain_view", "park_view", "quiet_street", "cul_de_sac", "gated_community",
    ],
    "nearby": [
        "near_schools", "near_transport", "near_parks", "near_hospitals",
        "near_shopping", "near_restaurants", "near_university", "near_beach",
    ],
    "condition": [
        "new_build", "recently_renovated", "period_property", "listed_building",
        "fixer_upper", "move_in_ready", "show_home_condition",
    ],
    "pet_lifestyle": [
        "pet_friendly", "garden_for_pets", "home_office", "utility_room",
        "study_room", "playroom", "basement", "wine_cellar", "cinema_room",
    ],
    "energy": [
        "solar_panels", "ev_charger", "underfloor_heating", "double_glazing",
        "triple_glazing", "air_conditioning", "smart_thermostat", "high_speed_broadband",
    ],
}

ALL_VALID_TAGS: set[str] = {tag for tags in VALID_TAGS.values() for tag in tags}


def validate_tags(tags: list[str]) -> tuple[list[str], list[str]]:
    """Split incoming tags into (valid, invalid) buckets."""
    valid = [t for t in tags if t in ALL_VALID_TAGS]
    invalid = [t for t in tags if t not in ALL_VALID_TAGS]
    return valid, invalid
