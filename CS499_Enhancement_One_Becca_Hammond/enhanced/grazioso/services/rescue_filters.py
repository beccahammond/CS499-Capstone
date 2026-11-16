# Becca Hammond
# CS499 Enhancement One - Software Design and Engineering
# 11/15/2026
# Version 1.0
#
# Purpose: Grazioso Salvare's rescue type criteria and the MongoDB queries
# built from them. In the original notebook these breed lists, sex values and
# age ranges were typed straight into an if/elif chain inside a Dash callback.
# Pulling them out here means the criteria have names, live in one place, and
# can be tested without starting the dashboard.

from typing import Dict, List, Tuple

from grazioso.exceptions import UnknownRescueTypeError

###########################
# Rescue type names
###########################
# These are the values the radio buttons send to the callback
WATER = "Water"
MOUNTAIN = "Mountain"
DISASTER = "Disaster"
RESET = "Reset"

# Labels shown on the dashboard, in the order they appear
RESCUE_TYPE_OPTIONS: List[Tuple[str, str]] = [
    (" Water Rescue", WATER),
    (" Mountain or Wilderness Rescue", MOUNTAIN),
    (" Disaster Rescue or Individual Tracking", DISASTER),
    (" Reset", RESET),
]

###########################
# Criteria from Grazioso Salvare's requirements
###########################
INTACT_FEMALE = "Intact Female"
INTACT_MALE = "Intact Male"

WATER_BREEDS = ("Labrador Retriever Mix", "Chesapeake Bay Retriever", "Newfoundland")
MOUNTAIN_BREEDS = ("German Shepherd", "Alaskan Malamute", "Old English Sheepdog",
                   "Siberian Husky", "Rottweiler")
DISASTER_BREEDS = ("Doberman Pinscher", "German Shepherd", "Golden Retriever",
                   "Bloodhound", "Rottweiler")

# Ages are in weeks to match the age_upon_outcome_in_weeks field
WATER_MIN_AGE_WEEKS, WATER_MAX_AGE_WEEKS = 26, 156
MOUNTAIN_MIN_AGE_WEEKS, MOUNTAIN_MAX_AGE_WEEKS = 26, 156
DISASTER_MIN_AGE_WEEKS, DISASTER_MAX_AGE_WEEKS = 20, 300

# One entry per rescue type. Adding a new rescue type means adding one entry
# here instead of another elif in the callback.
RESCUE_PROFILES: Dict[str, Dict] = {
    WATER: {
        "breeds": WATER_BREEDS,
        "sex": INTACT_FEMALE,
        "min_age_weeks": WATER_MIN_AGE_WEEKS,
        "max_age_weeks": WATER_MAX_AGE_WEEKS,
    },
    MOUNTAIN: {
        "breeds": MOUNTAIN_BREEDS,
        "sex": INTACT_MALE,
        "min_age_weeks": MOUNTAIN_MIN_AGE_WEEKS,
        "max_age_weeks": MOUNTAIN_MAX_AGE_WEEKS,
    },
    DISASTER: {
        "breeds": DISASTER_BREEDS,
        "sex": INTACT_MALE,
        "min_age_weeks": DISASTER_MIN_AGE_WEEKS,
        "max_age_weeks": DISASTER_MAX_AGE_WEEKS,
    },
}


def get_query(rescue_type: str) -> dict:
    """
    Return the MongoDB query for a rescue type.
    Reset returns an empty query, which matches every animal.
    Raises UnknownRescueTypeError for anything else. The original sent any
    value it didn't recognize down the Reset branch and returned the whole
    collection.
    """
    if rescue_type == RESET:
        return {}

    profile = RESCUE_PROFILES.get(rescue_type)
    if profile is None:
        raise UnknownRescueTypeError(f"Unknown rescue type: {rescue_type!r}")

    return {
        "breed": {"$in": list(profile["breeds"])},
        "sex_upon_outcome": profile["sex"],
        "age_upon_outcome_in_weeks": {"$gte": profile["min_age_weeks"],
                                      "$lte": profile["max_age_weeks"]},
    }
