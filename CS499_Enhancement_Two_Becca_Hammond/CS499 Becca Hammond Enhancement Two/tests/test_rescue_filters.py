# Becca Hammond
# CS499 Enhancement Two - Algorithms and Data Structures
# 11/16/2026
# Version 2.0
# Version 1.0 (11/15/2026): Enhancement One, Software Design and Engineering
#
# Purpose: Unit tests for the rescue type criteria and the queries built from
# them. Version 2.0 adds tests for profiles, mixes and unavailable dogs.

import pytest

from grazioso.exceptions import UnknownRescueTypeError
from grazioso.services import rescue_filters as rf


###########################
# Queries
###########################
def test_water_query_matches_requirements():
    query = rf.get_query(rf.WATER)
    assert query["sex_upon_outcome"] == "Intact Female"
    assert query["age_upon_outcome_in_weeks"] == {"$gte": 26, "$lte": 156}
    assert set(query["breed"]["$in"]) == {
        "Labrador Retriever", "Labrador Retriever Mix",
        "Chesapeake Bay Retriever", "Chesapeake Bay Retriever Mix",
        "Newfoundland", "Newfoundland Mix",
    }


def test_mountain_query_matches_requirements():
    query = rf.get_query(rf.MOUNTAIN)
    assert query["sex_upon_outcome"] == "Intact Male"
    assert query["age_upon_outcome_in_weeks"] == {"$gte": 26, "$lte": 156}
    assert "German Shepherd Mix" in query["breed"]["$in"]
    assert len(query["breed"]["$in"]) == 10


def test_disaster_query_matches_requirements():
    query = rf.get_query(rf.DISASTER)
    assert query["sex_upon_outcome"] == "Intact Male"
    assert query["age_upon_outcome_in_weeks"] == {"$gte": 20, "$lte": 300}
    assert "Bloodhound" in query["breed"]["$in"]


@pytest.mark.parametrize("rescue_type", [rf.WATER, rf.MOUNTAIN, rf.DISASTER])
def test_queries_leave_out_unavailable_dogs(rescue_type):
    assert rf.get_query(rescue_type)["outcome_type"] == {"$nin": list(rf.UNAVAILABLE_OUTCOMES)}


def test_reset_returns_empty_query():
    assert rf.get_query(rf.RESET) == {}


@pytest.mark.parametrize("bad_type", ["water", "Fire", "", None, 3])
def test_unknown_rescue_type_raises(bad_type):
    # The original treated anything it didn't recognize as Reset
    with pytest.raises(UnknownRescueTypeError):
        rf.get_query(bad_type)


def test_every_option_has_a_query():
    for _label, value in rf.RESCUE_TYPE_OPTIONS:
        assert isinstance(rf.get_query(value), dict)


def test_query_is_the_same_every_time():
    # A stable query keeps cache keys and results predictable
    assert rf.get_query(rf.MOUNTAIN) == rf.get_query(rf.MOUNTAIN)


###########################
# Profiles
###########################
def test_breed_weights_follow_preference_order():
    weights = rf.get_profile(rf.MOUNTAIN).breed_weights
    assert weights["German Shepherd"] == 1.0
    assert weights["Rottweiler"] == rf.LEAST_PREFERRED_BREED_WEIGHT
    ordered = [weights[breed] for breed in rf.MOUNTAIN_BREEDS]
    assert ordered == sorted(ordered, reverse=True)


def test_profile_ideal_age_is_middle_of_range():
    profile = rf.get_profile(rf.DISASTER)
    assert profile.ideal_age_weeks == 160
    assert profile.half_age_range == 140


def test_single_breed_profile_gets_full_weight():
    profile = rf._build_profile("Test", ("Poodle",), "Intact Male", 10, 20)
    assert profile.breed_weights == {"Poodle": 1.0}


def test_unknown_profile_raises():
    with pytest.raises(UnknownRescueTypeError):
        rf.get_profile("Fire")


###########################
# Against the sample database
###########################
def test_queries_run_against_the_database(shelter):
    assert [a["name"] for a in shelter.read(rf.get_query(rf.WATER))] == ["Daisy"]
    # Sarge is a German Shepherd Mix. The original exact match missed him.
    # Ghost was euthanized, so he is left out.
    assert sorted(a["name"] for a in shelter.read(rf.get_query(rf.MOUNTAIN))) == ["Sarge", "Zeke"]
    assert sorted(a["name"] for a in shelter.read(rf.get_query(rf.DISASTER))) == ["Boomer", "Sarge", "Zeke"]
