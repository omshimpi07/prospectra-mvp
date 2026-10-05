"""Canonical category taxonomy and normalization.

Provides a centralized deterministic vocabulary for target business categories.
AI extraction output must be mapped and validated against this vocabulary to prevent
arbitrary categorization strings and prepare for downstream Overture taxonomy mapping.
"""

from typing import Final

CANONICAL_CATEGORIES: Final[set[str]] = {
    "restaurant",
    "cafe",
    "bakery",
    "bar",
    "pub",
    "salon",
    "spa",
    "gym",
    "fitness_center",
    "dental_clinic",
    "medical_clinic",
    "pharmacy",
    "retail_store",
    "boutique",
    "grocery_store",
    "auto_repair",
    "real_estate_agency",
    "coworking_space",
    "hotel",
    "consulting_firm",
    "marketing_agency",
    "software_agency",
    "school",
    "tutoring_center",
}

# Common alias/synonym mappings to canonical categories
CATEGORY_ALIASES: Final[dict[str, str]] = {
    "restaurants": "restaurant",
    "food_joint": "restaurant",
    "eatery": "restaurant",
    "cafes": "cafe",
    "coffee_shop": "cafe",
    "bakeries": "bakery",
    "bars": "bar",
    "pubs": "pub",
    "salons": "salon",
    "hair_salon": "salon",
    "beauty_parlor": "salon",
    "beauty_parlour": "salon",
    "spas": "spa",
    "gyms": "gym",
    "fitness": "fitness_center",
    "fitness_centre": "fitness_center",
    "dentist": "dental_clinic",
    "dentists": "dental_clinic",
    "dental": "dental_clinic",
    "clinic": "medical_clinic",
    "clinics": "medical_clinic",
    "doctor": "medical_clinic",
    "pharmacies": "pharmacy",
    "chemist": "pharmacy",
    "drugstore": "pharmacy",
    "retail": "retail_store",
    "shops": "retail_store",
    "shop": "retail_store",
    "boutiques": "boutique",
    "supermarket": "grocery_store",
    "grocery": "grocery_store",
    "groceries": "grocery_store",
    "mechanic": "auto_repair",
    "car_repair": "auto_repair",
    "garage": "auto_repair",
    "real_estate": "real_estate_agency",
    "realtor": "real_estate_agency",
    "property_dealer": "real_estate_agency",
    "coworking": "coworking_space",
    "co_working": "coworking_space",
    "hotels": "hotel",
    "hospitality": "hotel",
    "consultancy": "consulting_firm",
    "consultants": "consulting_firm",
    "marketing": "marketing_agency",
    "digital_marketing": "marketing_agency",
    "software": "software_agency",
    "it_services": "software_agency",
    "dev_agency": "software_agency",
    "schools": "school",
    "coaching": "tutoring_center",
    "coaching_class": "tutoring_center",
    "tuition": "tutoring_center",
}


def normalize_category(raw_category: str) -> str | None:
    """Normalize a raw category string and match against canonical categories.

    Returns the canonical category name or None if no match is found.
    """
    cleaned = raw_category.strip().lower().replace("-", "_").replace(" ", "_")
    if cleaned in CANONICAL_CATEGORIES:
        return cleaned
    return CATEGORY_ALIASES.get(cleaned)


def validate_and_normalize_categories(categories: list[str]) -> list[str]:
    """Validate and normalize a list of category strings against canonical taxonomy.

    Preserves unique canonical categories in order of appearance.
    Invalid or unrecognized categories are discarded.
    """
    seen: set[str] = set()
    normalized: list[str] = []
    for cat in categories:
        canonical = normalize_category(cat)
        if canonical and canonical not in seen:
            seen.add(canonical)
            normalized.append(canonical)
    return normalized
