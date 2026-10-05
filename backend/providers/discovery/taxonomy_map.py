"""Mapping from external provider taxonomies to Prospectra canonical categories."""

from typing import Final

from backend.models.categories import CANONICAL_CATEGORIES

# Overture taxonomy.primary (or basic_category) -> Prospectra canonical category
OVERTURE_TO_CANONICAL: Final[dict[str, str]] = {
    # Cafes & Bakeries
    "coffee_shop": "cafe",
    "cafe": "cafe",
    "tea_house": "cafe",
    "tea_room": "cafe",
    "bakery": "bakery",
    "pastry_shop": "bakery",
    # Restaurants & Dining
    "restaurant": "restaurant",
    "fast_food_restaurant": "restaurant",
    "pizza_restaurant": "restaurant",
    "diner": "restaurant",
    "bistro": "restaurant",
    "bar_and_grill": "restaurant",
    "food_court": "restaurant",
    "caterer": "restaurant",
    # Bars & Nightlife
    "bar": "bar",
    "cocktail_bar": "bar",
    "wine_bar": "bar",
    "beer_bar": "bar",
    "pub": "pub",
    "gastropub": "pub",
    "brewery": "pub",
    # Personal Care & Beauty
    "hair_salon": "salon",
    "beauty_salon": "salon",
    "barber_shop": "salon",
    "nail_salon": "salon",
    "spa": "spa",
    "day_spa": "spa",
    "health_spa": "spa",
    # Health & Fitness
    "gym": "gym",
    "fitness_center": "fitness_center",
    "yoga_studio": "fitness_center",
    "pilates_studio": "fitness_center",
    # Healthcare
    "dentist": "dental_clinic",
    "dental_clinic": "dental_clinic",
    "medical_clinic": "medical_clinic",
    "doctor": "medical_clinic",
    "hospital": "medical_clinic",
    "urgent_care_clinic": "medical_clinic",
    "pharmacy": "pharmacy",
    "drugstore": "pharmacy",
    # Retail & Grocery
    "retail_store": "retail_store",
    "clothing_store": "retail_store",
    "department_store": "retail_store",
    "shoe_store": "retail_store",
    "boutique": "boutique",
    "grocery_store": "grocery_store",
    "supermarket": "grocery_store",
    "convenience_store": "grocery_store",
    # Automotive
    "auto_repair": "auto_repair",
    "mechanic": "auto_repair",
    "car_repair": "auto_repair",
    # Real Estate & Coworking
    "real_estate_agency": "real_estate_agency",
    "coworking_space": "coworking_space",
    # Hospitality
    "hotel": "hotel",
    "motel": "hotel",
    "resort": "hotel",
    # Professional Services
    "consulting_firm": "consulting_firm",
    "marketing_agency": "marketing_agency",
    "advertising_agency": "marketing_agency",
    "software_company": "software_agency",
    "it_services": "software_agency",
    # Education
    "school": "school",
    "college": "school",
    "university": "school",
    "tutoring_service": "tutoring_center",
    "learning_center": "tutoring_center",
}


def map_overture_category(raw_category: str | None) -> str | None:
    """Map an Overture place category to a Prospectra canonical category."""
    if not raw_category:
        return None
    cleaned = raw_category.strip().lower().replace("-", "_").replace(" ", "_")
    if cleaned in CANONICAL_CATEGORIES:
        return cleaned
    return OVERTURE_TO_CANONICAL.get(cleaned)
