# Becca Hammond
# CS499 Enhancement Two - Algorithms and Data Structures
# 11/16/2026
# Version 2.0
#
# Purpose: Ranks rescue candidates so staff see the best fits first. The
# original dashboard treated every dog that matched a filter as equal and
# listed them in whatever order MongoDB returned them.
#
# How a dog is scored (0 to 1, higher is better):
#   breed score: the breed's preference weight from the rescue profile,
#                multiplied by MIX_FACTOR if the dog is a mix
#   age score:   1.0 at the ideal training age, falling to 0.0 at either end
#                of the allowed range
#   score = BREED_WEIGHT * breed score + AGE_WEIGHT * age score
#
# Sex is still a hard requirement in the query, not part of the score,
# because it is Grazioso Salvare's rule for each rescue type.
#
# Picking the top k:
#   Sorting every candidate costs O(n log n). Keeping a min-heap of size k
#   costs O(n log k), because each dog is compared with the smallest score in
#   the heap and only replaces it when it scores higher. Memory is O(k)
#   instead of O(n), so candidates can be read straight from the database
#   cursor one at a time without loading them all into a list.

import heapq
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, List, Tuple

from grazioso.services.rescue_filters import MIX_SUFFIX, RescueProfile

###########################
# Scoring settings
###########################
BREED_WEIGHT = 0.6
AGE_WEIGHT = 0.4
# A mix of a preferred breed is still a candidate, but scores lower than the
# purebred
MIX_FACTOR = 0.8
DEFAULT_TOP_K = 10
SCORE_DECIMALS = 3


def breed_score(breed: str, profile: RescueProfile) -> float:
    """ Preference weight for a breed, lowered for mixes. O(1) dict lookup. """
    if not breed:
        return 0.0
    if breed.endswith(MIX_SUFFIX):
        base = breed[: -len(MIX_SUFFIX)]
        return profile.breed_weights.get(base, 0.0) * MIX_FACTOR
    return profile.breed_weights.get(breed, 0.0)


def age_score(age_weeks, profile: RescueProfile) -> float:
    """ 1.0 at the ideal age, 0.0 at the edges of the range or outside it """
    try:
        age = float(age_weeks)
    except (TypeError, ValueError):
        return 0.0

    # Guard against dividing by zero if a profile ever has min == max. In
    # that case only the exact age counts.
    half_range = profile.half_age_range
    if half_range <= 0:
        return 1.0 if age == profile.ideal_age_weeks else 0.0

    distance = abs(age - profile.ideal_age_weeks)
    return max(0.0, 1.0 - distance / half_range)


def score_dog(dog: dict, profile: RescueProfile) -> float:
    """ Weighted suitability score for one dog. O(1) per dog. """
    score = (BREED_WEIGHT * breed_score(dog.get("breed", ""), profile)
             + AGE_WEIGHT * age_score(dog.get("age_upon_outcome_in_weeks"), profile))
    return round(score, SCORE_DECIMALS)


@dataclass
class RankingResult:
    """ What one pass over the candidates produces """
    top: List[dict]
    total: int
    breed_counts: Counter = field(default_factory=Counter)


def rank_candidates(dogs: Iterable[dict], profile: RescueProfile,
                    k: int = DEFAULT_TOP_K) -> RankingResult:
    """
    Score every candidate and keep the k best, in one pass.

    Time:   O(n log k) for n candidates. Each push or replace on a heap of
            size k is O(log k). The final sort of the k winners is O(k log k).
    Memory: O(k + b), where b is the number of distinct breeds counted for
            the chart. The candidates themselves are never all held at once.

    The same pass also counts breeds for the pie chart, so the data is read
    once instead of once for the table and again for the chart.
    """
    if k <= 0:
        raise ValueError("k must be greater than 0")

    # Min-heap of (score, tie_breaker, index, dog). The smallest score sits at
    # heap[0], so it is the one replaced when a better dog shows up.
    # tie_breaker puts the lower rec_num ahead when scores are equal, and
    # index keeps Python from ever comparing two dicts.
    heap: List[Tuple[float, float, int, dict]] = []
    breed_counts: Counter = Counter()
    total = 0

    for index, dog in enumerate(dogs):
        total += 1
        breed_counts[dog.get("breed", "Unknown")] += 1

        score = score_dog(dog, profile)
        rec_num = dog.get("rec_num")
        tie_breaker = -float(rec_num) if isinstance(rec_num, (int, float)) else -float(index)
        entry = (score, tie_breaker, index, dog)

        if len(heap) < k:
            heapq.heappush(heap, entry)             # O(log k)
        elif entry[:2] > heap[0][:2]:
            heapq.heapreplace(heap, entry)          # O(log k)

    # Highest score first. Only k items, so O(k log k).
    winners = sorted(heap, key=lambda item: item[:2], reverse=True)
    top = []
    for rank, (score, _tie, _index, dog) in enumerate(winners, start=1):
        row = dict(dog)
        row["rank"] = rank
        row["suitability_score"] = score
        top.append(row)

    return RankingResult(top=top, total=total, breed_counts=breed_counts)


def top_breeds(breeds: Iterable[str], n: int) -> List[Tuple[str, int]]:
    """
    Count breeds and return the n most common.
    Counting is O(m) for m values. heapq.nlargest picks the top n from b
    distinct breeds in O(b log n), which beats sorting all b breeds.
    """
    counts = Counter(breeds)
    return heapq.nlargest(n, counts.items(), key=lambda item: item[1])
