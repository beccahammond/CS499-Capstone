# Becca Hammond
# CS499 Enhancement Two - Algorithms and Data Structures
# 11/16/2026
# Version 2.0
#
# Purpose: Times the original CS 340 approach against the Enhancement Two
# approach on the same data, so the Big O claims in the code comments are
# backed by measurements.
#
# Usage (from the project folder):
#     python benchmarks/benchmark_enhancement_two.py --csv path/to/aac_shelter_outcomes.csv
#         Loads the CSV into mongomock (an in-memory MongoDB) and runs there
#     python benchmarks/benchmark_enhancement_two.py --live
#         Runs against the real MongoDB in your .env settings
#
# What it measures:
#   1. Reset view: loading all records into a DataFrame (original) against
#      loading one page with keyset pagination
#   2. Breed chart: DataFrame value_counts on every record (original) against
#      one streaming Counter pass, and against a cache hit
#   3. Rescue view: the original exact-match query against streaming plus
#      top-k ranking, including how many candidates each finds
#   4. Top-k on its own: full sort against a min-heap as n grows
#   5. Peak memory for the Reset view, measured with tracemalloc

import argparse
import csv
import heapq
import random
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grazioso.callbacks import BREED_ONLY_PROJECTION, NO_ID_PROJECTION  # noqa: E402
from grazioso.data.animal_shelter import AnimalShelter  # noqa: E402
from grazioso.services import rescue_filters as rf  # noqa: E402
from grazioso.services.cache import TTLCache  # noqa: E402
from grazioso.services.ranking import rank_candidates, top_breeds  # noqa: E402

RUNS = 15
PAGE_SIZE = 10
NUMERIC_FIELDS = {"rec_num": int, "age_upon_outcome_in_weeks": float,
                  "location_lat": float, "location_long": float}

# The original CS 340 water rescue query, copied from ProjectTwoDashboard.ipynb
ORIGINAL_WATER_QUERY = {
    "breed": {"$in": ["Labrador Retriever Mix", "Chesapeake Bay Retriever", "Newfoundland"]},
    "sex_upon_outcome": "Intact Female",
    "age_upon_outcome_in_weeks": {"$gte": 26, "$lte": 156},
}
ORIGINAL_QUERIES = {
    rf.WATER: ORIGINAL_WATER_QUERY,
    rf.MOUNTAIN: {"breed": {"$in": list(rf.MOUNTAIN_BREEDS)}, "sex_upon_outcome": "Intact Male",
                  "age_upon_outcome_in_weeks": {"$gte": 26, "$lte": 156}},
    rf.DISASTER: {"breed": {"$in": list(rf.DISASTER_BREEDS)}, "sex_upon_outcome": "Intact Male",
                  "age_upon_outcome_in_weeks": {"$gte": 20, "$lte": 300}},
}


def median_ms(function, runs=RUNS):
    """ Run function several times and return the median time in milliseconds """
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        function()
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times)


def load_csv_into_mongomock(csv_path):
    import mongomock
    with open(csv_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for name, convert in NUMERIC_FIELDS.items():
            try:
                row[name] = convert(row[name])
            except (KeyError, ValueError):
                pass
    shelter = AnimalShelter("bench", "bench", client=mongomock.MongoClient())
    shelter.collection.insert_many(rows)
    return shelter, "mongomock with " + Path(csv_path).name


def connect_live():
    from app import connect
    from grazioso.config import load_config
    shelter = connect(load_config())
    shelter.ping()
    return shelter, "live MongoDB"


###########################
# The original CS 340 approach
###########################
def original_reset(shelter):
    df = pd.DataFrame.from_records(shelter.read({}))
    df.drop(columns=["_id"], inplace=True)
    return df.to_dict("records")


def original_chart(records):
    return pd.DataFrame.from_dict(records)["breed"].value_counts().head(10)


def original_rescue(shelter, rescue_type):
    df = pd.DataFrame.from_records(shelter.read(ORIGINAL_QUERIES[rescue_type]))
    if not df.empty:
        df.drop(columns=["_id"], inplace=True)
    return df.to_dict("records")


###########################
# The Enhancement Two approach
###########################
def new_reset_page(shelter, after_id=None):
    documents, last_id = shelter.read_page({}, after_id, PAGE_SIZE)
    return [{k: v for k, v in d.items() if k != "_id"} for d in documents], last_id


def new_chart(shelter):
    return top_breeds((d.get("breed") for d in shelter.iterate({}, BREED_ONLY_PROJECTION)), 10)


def new_rescue(shelter, rescue_type):
    query = rf.get_query(rescue_type)
    return rank_candidates(shelter.iterate(query, NO_ID_PROJECTION), rf.get_profile(rescue_type), 10)


def peak_memory_kb(function):
    tracemalloc.start()
    function()
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak / 1024


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--csv", help="path to aac_shelter_outcomes.csv")
    group.add_argument("--live", action="store_true", help="use the MongoDB in .env")
    args = parser.parse_args()

    shelter, source = connect_live() if args.live else load_csv_into_mongomock(args.csv)
    total = shelter.count({})
    print(f"Data source: {source} ({total:,} records), median of {RUNS} runs")
    if not args.live:
        print("Mongomock has no real indexes and scans every record, so page timings are")
        print("slower than a real MongoDB server. Use --live for real page timings.")
    print()

    # 1. Reset view
    print("1. Reset view")
    old_ms = median_ms(lambda: original_reset(shelter))
    first_ms = median_ms(lambda: new_reset_page(shelter))
    # A cursor about halfway through, to time a page deep in the collection
    after = None
    for _ in range(total // PAGE_SIZE // 2):
        _rows, after = new_reset_page(shelter, after)
    deep_ms = median_ms(lambda: new_reset_page(shelter, after))
    print(f"   Original, load all {total:,} records:     {old_ms:8.2f} ms")
    print(f"   Keyset, first page of {PAGE_SIZE}:              {first_ms:8.2f} ms")
    print(f"   Keyset, page {total // PAGE_SIZE // 2 + 1} (halfway):           {deep_ms:8.2f} ms\n")

    # 2. Breed chart
    print("2. Breed chart (top 10 breeds in all records)")
    records = original_reset(shelter)
    chart_old = median_ms(lambda: original_chart(records))
    chart_new = median_ms(lambda: new_chart(shelter))
    cache = TTLCache()
    cache.put("breeds", new_chart(shelter))
    chart_hit = median_ms(lambda: cache.get("breeds"))
    old_top = list(original_chart(records).items())
    same = [b for b, _ in old_top] == [b for b, _ in new_chart(shelter)]
    print(f"   Original value_counts, data already loaded: {chart_old:8.2f} ms (repeated on every table change)")
    print(f"   Streaming Counter pass from the database:  {chart_new:8.2f} ms (once per minute)")
    print(f"   Cache hit:                                 {chart_hit:8.4f} ms")
    print(f"   Same top 10 breeds as the original:        {same}\n")

    # 3. Rescue views
    print("3. Rescue views")
    for rescue_type in (rf.WATER, rf.MOUNTAIN, rf.DISASTER):
        old_rows = original_rescue(shelter, rescue_type)
        result = new_rescue(shelter, rescue_type)
        old_ms = median_ms(lambda: original_rescue(shelter, rescue_type))
        new_ms = median_ms(lambda: new_rescue(shelter, rescue_type))
        unavailable = sum(1 for r in old_rows if r.get("outcome_type") in rf.UNAVAILABLE_OUTCOMES)
        print(f"   {rescue_type:9} original: {len(old_rows):3} matches, {unavailable} unavailable, "
              f"unranked, {old_ms:6.2f} ms | new: {result.total:3} available candidates, "
              f"top {len(result.top)} ranked, {new_ms:6.2f} ms")
    print()

    # 4. Top-k on its own
    print("4. Picking the top 10: full sort O(n log n) against min-heap O(n log k)")
    rng = random.Random(13)
    for n in (10_000, 100_000, 1_000_000):
        scores = [rng.random() for _ in range(n)]
        sort_ms = median_ms(lambda: sorted(scores, reverse=True)[:10], runs=5)
        heap_ms = median_ms(lambda: heapq.nlargest(10, scores), runs=5)
        print(f"   n = {n:>9,}   full sort {sort_ms:8.2f} ms   heap {heap_ms:8.2f} ms   "
              f"heap is {sort_ms / heap_ms:4.1f}x faster")
    print()

    # 5. Peak memory
    print("5. Peak memory for the Reset view")
    old_kb = peak_memory_kb(lambda: original_reset(shelter))
    new_kb = peak_memory_kb(lambda: new_reset_page(shelter))
    print(f"   Original, all records: {old_kb:10,.0f} KB")
    print(f"   Keyset, one page:      {new_kb:10,.0f} KB")


if __name__ == "__main__":
    main()
