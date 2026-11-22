# Becca Hammond
# CS499 Enhancement Two - Algorithms and Data Structures
# 11/16/2026
# Version 2.0
#
# Purpose: Unit tests for suitability scoring and top-k ranking. The heap
# results are checked against a plain full sort, which is the simple O(n log n)
# answer the heap is replacing.

import random

import pytest

from grazioso.services import rescue_filters as rf
from grazioso.services.ranking import (AGE_WEIGHT, BREED_WEIGHT, MIX_FACTOR, age_score,
                                       breed_score, rank_candidates, score_dog, top_breeds)

MOUNTAIN = rf.get_profile(rf.MOUNTAIN)


###########################
# Scoring
###########################
def test_breed_score_uses_preference_weight():
    assert breed_score("German Shepherd", MOUNTAIN) == 1.0
    assert breed_score("Rottweiler", MOUNTAIN) == rf.LEAST_PREFERRED_BREED_WEIGHT


def test_mix_scores_lower_than_purebred():
    assert breed_score("German Shepherd Mix", MOUNTAIN) == pytest.approx(MIX_FACTOR)
    assert breed_score("German Shepherd Mix", MOUNTAIN) < breed_score("German Shepherd", MOUNTAIN)


@pytest.mark.parametrize("breed", ["Poodle", "", None])
def test_unlisted_breed_scores_zero(breed):
    assert breed_score(breed, MOUNTAIN) == 0.0


def test_age_score_peaks_at_ideal_age():
    assert age_score(MOUNTAIN.ideal_age_weeks, MOUNTAIN) == 1.0
    assert age_score(MOUNTAIN.min_age_weeks, MOUNTAIN) == 0.0
    assert age_score(MOUNTAIN.max_age_weeks, MOUNTAIN) == 0.0
    assert 0 < age_score(MOUNTAIN.ideal_age_weeks + 10, MOUNTAIN) < 1


@pytest.mark.parametrize("bad_age", [None, "two years", float("nan")])
def test_age_score_handles_bad_values(bad_age):
    assert age_score(bad_age, MOUNTAIN) == 0.0


def test_age_score_avoids_divide_by_zero():
    # A profile where min and max are the same has no range to divide by
    profile = rf._build_profile("Test", ("Poodle",), "Intact Male", 50, 50)
    assert age_score(50, profile) == 1.0
    assert age_score(51, profile) == 0.0


def test_score_combines_breed_and_age():
    dog = {"breed": "German Shepherd", "age_upon_outcome_in_weeks": MOUNTAIN.ideal_age_weeks}
    assert score_dog(dog, MOUNTAIN) == pytest.approx(BREED_WEIGHT + AGE_WEIGHT)


###########################
# Top-k ranking
###########################
def _random_dogs(count, seed=13):
    rng = random.Random(seed)
    breeds = list(rf.MOUNTAIN_BREEDS) + [b + " Mix" for b in rf.MOUNTAIN_BREEDS]
    return [{"rec_num": i, "breed": rng.choice(breeds),
             "age_upon_outcome_in_weeks": rng.uniform(26, 156)} for i in range(count)]


@pytest.mark.parametrize("count,k", [(0, 5), (3, 10), (100, 10), (2000, 25)])
def test_heap_matches_full_sort(count, k):
    dogs = _random_dogs(count)
    expected = sorted(dogs, key=lambda d: (score_dog(d, MOUNTAIN), -d["rec_num"]), reverse=True)[:k]
    result = rank_candidates(iter(dogs), MOUNTAIN, k)
    assert [d["rec_num"] for d in result.top] == [d["rec_num"] for d in expected]
    assert result.total == count


def test_ranks_are_numbered_and_scores_descend():
    result = rank_candidates(_random_dogs(50), MOUNTAIN, 10)
    assert [d["rank"] for d in result.top] == list(range(1, 11))
    scores = [d["suitability_score"] for d in result.top]
    assert scores == sorted(scores, reverse=True)


def test_ties_go_to_the_lower_record_number():
    dogs = [{"rec_num": n, "breed": "German Shepherd", "age_upon_outcome_in_weeks": 91}
            for n in (30, 10, 20)]
    assert [d["rec_num"] for d in rank_candidates(dogs, MOUNTAIN, 2).top] == [10, 20]


def test_ranking_counts_every_breed_not_only_the_top():
    dogs = _random_dogs(200)
    result = rank_candidates(dogs, MOUNTAIN, 5)
    assert sum(result.breed_counts.values()) == 200


def test_ranking_does_not_change_the_input():
    dogs = _random_dogs(5)
    rank_candidates(dogs, MOUNTAIN, 3)
    assert all("rank" not in dog for dog in dogs)


def test_ranking_works_on_a_one_pass_iterator():
    # The cursor from MongoDB can only be read once, so neither can this
    stream = (dog for dog in _random_dogs(30))
    assert len(rank_candidates(stream, MOUNTAIN, 5).top) == 5


def test_k_must_be_positive():
    with pytest.raises(ValueError):
        rank_candidates([], MOUNTAIN, 0)


###########################
# Top breeds
###########################
def test_top_breeds_returns_most_common_first():
    breeds = ["A"] * 5 + ["B"] * 3 + ["C"] * 7 + ["D"]
    assert top_breeds(breeds, 2) == [("C", 7), ("A", 5)]


def test_top_breeds_with_fewer_breeds_than_requested():
    assert top_breeds(["A", "A", "B"], 10) == [("A", 2), ("B", 1)]
