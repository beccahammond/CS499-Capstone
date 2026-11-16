# Becca Hammond
# CS499 Enhancement One - Software Design and Engineering
# 11/15/2026
# Version 1.0
#
# Purpose: Unit tests for the rescue type criteria. These rules used to be
# buried in a Dash callback, so they could only be checked by clicking
# through the dashboard.

import pytest

from grazioso.exceptions import UnknownRescueTypeError
from grazioso.services import rescue_filters as rf


def test_water_query_matches_requirements():
    assert rf.get_query(rf.WATER) == {
        "breed": {"$in": ["Labrador Retriever Mix", "Chesapeake Bay Retriever", "Newfoundland"]},
        "sex_upon_outcome": "Intact Female",
        "age_upon_outcome_in_weeks": {"$gte": 26, "$lte": 156},
    }


def test_mountain_query_matches_requirements():
    query = rf.get_query(rf.MOUNTAIN)
    assert query["breed"]["$in"] == ["German Shepherd", "Alaskan Malamute", "Old English Sheepdog",
                                     "Siberian Husky", "Rottweiler"]
    assert query["sex_upon_outcome"] == "Intact Male"
    assert query["age_upon_outcome_in_weeks"] == {"$gte": 26, "$lte": 156}


def test_disaster_query_matches_requirements():
    query = rf.get_query(rf.DISASTER)
    assert query["breed"]["$in"] == ["Doberman Pinscher", "German Shepherd", "Golden Retriever",
                                     "Bloodhound", "Rottweiler"]
    assert query["sex_upon_outcome"] == "Intact Male"
    assert query["age_upon_outcome_in_weeks"] == {"$gte": 20, "$lte": 300}


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


def test_queries_run_against_the_database(shelter):
    assert [a["name"] for a in shelter.read(rf.get_query(rf.WATER))] == ["Daisy"]
    assert [a["name"] for a in shelter.read(rf.get_query(rf.MOUNTAIN))] == ["Zeke"]
    assert sorted(a["name"] for a in shelter.read(rf.get_query(rf.DISASTER))) == ["Boomer", "Zeke"]


def test_query_is_a_new_copy_each_time():
    # Changing one query should never change the stored criteria
    query = rf.get_query(rf.WATER)
    query["breed"]["$in"].append("Poodle")
    assert "Poodle" not in rf.get_query(rf.WATER)["breed"]["$in"]
