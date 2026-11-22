# Becca Hammond
# CS499 Enhancement Two - Algorithms and Data Structures
# 11/16/2026
# Version 2.0
# Version 1.0 (11/15/2026): criteria moved out of the callback into named constants
#
# Purpose: Grazioso Salvare's rescue type criteria and the MongoDB queries
# built from them.
#
# Changes in Version 2.0:
#   - Each rescue type has a profile with a breed preference order and an
#     ideal training age, used by ranking.py to score candidates
#   - Mixes of a preferred breed now match. The original exact match missed
#     dogs listed as "German Shepherd Mix", which are most of the candidates.
#   - Dogs that died, were euthanized, were disposed of or went missing are
#     left out, since staff can't train them
#   - Breed lists are stored as dictionaries and sets so lookups are O(1)

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Tuple

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

# Outcomes that mean the dog can't be trained. Every record in the data is an
# outcome, so this removes the ones where the dog is gone for good.
UNAVAILABLE_OUTCOMES: Tuple[str, ...] = ("Euthanasia", "Died", "Disposal", "Missing")

MIX_SUFFIX = " Mix"

# Breeds are listed in order of preference, most preferred first. The water
# list used to name "Labrador Retriever Mix" directly. Now every breed matches
# both the purebred and the mix.
WATER_BREEDS = ("Labrador Retriever", "Chesapeake Bay Retriever", "Newfoundland")
MOUNTAIN_BREEDS = ("German Shepherd", "Alaskan Malamute", "Old English Sheepdog",
                   "Siberian Husky", "Rottweiler")
DISASTER_BREEDS = ("Doberman Pinscher", "German Shepherd", "Golden Retriever",
                   "Bloodhound", "Rottweiler")

# Ages are in weeks to match the age_upon_outcome_in_weeks field
WATER_MIN_AGE_WEEKS, WATER_MAX_AGE_WEEKS = 26, 156
MOUNTAIN_MIN_AGE_WEEKS, MOUNTAIN_MAX_AGE_WEEKS = 26, 156
DISASTER_MIN_AGE_WEEKS, DISASTER_MAX_AGE_WEEKS = 20, 300

# The most preferred breed scores 1.0 and the least preferred scores this value
LEAST_PREFERRED_BREED_WEIGHT = 0.5


@dataclass(frozen=True)
class RescueProfile:
    """ Everything needed to query and rank candidates for one rescue type """
    name: str
    breeds: Tuple[str, ...]
    sex: str
    min_age_weeks: float
    max_age_weeks: float
    # breed -> preference weight. A dict gives O(1) lookups when scoring each
    # dog, where searching the tuple would be O(b) for b breeds.
    breed_weights: Dict[str, float] = field(default_factory=dict)
    # Every breed name the query accepts, purebred and mix. Stored as a set
    # so checking a breed is O(1).
    accepted_breeds: FrozenSet[str] = frozenset()

    @property
    def ideal_age_weeks(self) -> float:
        # The middle of the allowed range is treated as the ideal training age
        return (self.min_age_weeks + self.max_age_weeks) / 2

    @property
    def half_age_range(self) -> float:
        return (self.max_age_weeks - self.min_age_weeks) / 2


def _build_profile(name: str, breeds: Tuple[str, ...], sex: str,
                   min_age: float, max_age: float) -> RescueProfile:
    # Spread the weights evenly from 1.0 down to LEAST_PREFERRED_BREED_WEIGHT.
    # With one breed there is nothing to spread, so it gets 1.0.
    count = len(breeds)
    step = (1 - LEAST_PREFERRED_BREED_WEIGHT) / (count - 1) if count > 1 else 0
    weights = {breed: round(1 - i * step, 3) for i, breed in enumerate(breeds)}
    accepted = frozenset(breeds) | frozenset(breed + MIX_SUFFIX for breed in breeds)
    return RescueProfile(name, breeds, sex, min_age, max_age, weights, accepted)


# One entry per rescue type. Adding a new rescue type means adding one entry
# here instead of another elif in the callback.
RESCUE_PROFILES: Dict[str, RescueProfile] = {
    WATER: _build_profile(WATER, WATER_BREEDS, INTACT_FEMALE,
                          WATER_MIN_AGE_WEEKS, WATER_MAX_AGE_WEEKS),
    MOUNTAIN: _build_profile(MOUNTAIN, MOUNTAIN_BREEDS, INTACT_MALE,
                             MOUNTAIN_MIN_AGE_WEEKS, MOUNTAIN_MAX_AGE_WEEKS),
    DISASTER: _build_profile(DISASTER, DISASTER_BREEDS, INTACT_MALE,
                             DISASTER_MIN_AGE_WEEKS, DISASTER_MAX_AGE_WEEKS),
}


def get_profile(rescue_type: str) -> RescueProfile:
    """ Return the profile for a rescue type, or raise UnknownRescueTypeError """
    profile = RESCUE_PROFILES.get(rescue_type)
    if profile is None:
        raise UnknownRescueTypeError(f"Unknown rescue type: {rescue_type!r}")
    return profile


def get_query(rescue_type: str) -> dict:
    """
    Return the MongoDB query for a rescue type.
    Reset returns an empty query, which matches every animal.
    Raises UnknownRescueTypeError for anything else.
    """
    if rescue_type == RESET:
        return {}

    profile = get_profile(rescue_type)
    return {
        # sorted() keeps the query the same every time, which also keeps
        # cache keys and test results stable
        "breed": {"$in": sorted(profile.accepted_breeds)},
        "sex_upon_outcome": profile.sex,
        "age_upon_outcome_in_weeks": {"$gte": profile.min_age_weeks,
                                      "$lte": profile.max_age_weeks},
        "outcome_type": {"$nin": list(UNAVAILABLE_OUTCOMES)},
    }
