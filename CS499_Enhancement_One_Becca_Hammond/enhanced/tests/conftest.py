# Becca Hammond
# CS499 Enhancement One - Software Design and Engineering
# 11/15/2026
# Version 1.0
#
# Purpose: Shared pytest fixtures. mongomock stands in for a real MongoDB
# server, so the tests run anywhere, including GitHub Actions, without a
# database or a password.

import sys
from pathlib import Path

import mongomock
import pytest

# Let the tests import grazioso and app from the project folder
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grazioso.data.animal_shelter import AnimalShelter  # noqa: E402

# A few sample animals shaped like the Austin Animal Center records
SAMPLE_ANIMALS = [
    {"rec_num": 1, "name": "Daisy", "animal_type": "Dog", "breed": "Labrador Retriever Mix",
     "sex_upon_outcome": "Intact Female", "age_upon_outcome_in_weeks": 52.6,
     "outcome_type": "Return to Owner", "location_lat": 30.51, "location_long": -97.61},
    {"rec_num": 2, "name": "Zeke", "animal_type": "Dog", "breed": "Rottweiler",
     "sex_upon_outcome": "Intact Male", "age_upon_outcome_in_weeks": 120.9,
     "outcome_type": "Return to Owner", "location_lat": 30.47, "location_long": -97.56},
    {"rec_num": 3, "name": "Boomer", "animal_type": "Dog", "breed": "Bloodhound",
     "sex_upon_outcome": "Intact Male", "age_upon_outcome_in_weeks": 209.1,
     "outcome_type": "Return to Owner", "location_lat": 30.27, "location_long": -97.59},
    {"rec_num": 4, "name": "Kitty", "animal_type": "Cat", "breed": "Siamese Mix",
     "sex_upon_outcome": "Intact Female", "age_upon_outcome_in_weeks": 30.8,
     "outcome_type": "Adoption", "location_lat": 30.32, "location_long": -97.72},
    {"rec_num": 5, "name": "Pup", "animal_type": "Dog", "breed": "Labrador Retriever Mix",
     "sex_upon_outcome": "Intact Female", "age_upon_outcome_in_weeks": 10.0,
     "outcome_type": "Adoption", "location_lat": 30.40, "location_long": -97.50},
]


@pytest.fixture
def mock_client():
    return mongomock.MongoClient()


@pytest.fixture
def shelter(mock_client):
    shelter = AnimalShelter("testuser", "testpass", client=mock_client)
    shelter.collection.insert_many([dict(animal) for animal in SAMPLE_ANIMALS])
    return shelter
