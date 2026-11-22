# Becca Hammond
# CS499 Enhancement Two - Algorithms and Data Structures
# 11/16/2026
# Version 2.0
# Version 1.0 (11/15/2026): Enhancement One, Software Design and Engineering
#
# Purpose: Tests for the callback logic and the app startup. The callbacks
# call plain functions, so they can be tested here without a browser.
# Version 2.0 covers the ranked rescue views, keyset paging for Reset, the
# cached breed chart and the O(1) map lookup.

from unittest.mock import MagicMock

import mongomock
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from app import create_app
from grazioso.callbacks import (ALL_RECORDS_CHART_TITLE, build_map, build_row_highlight,
                                get_page, load_breed_chart, load_table)
from grazioso.data.animal_shelter import AnimalShelter
from grazioso.layout import TABLE_PAGE_SIZE
from grazioso.services import rescue_filters as rf
from grazioso.services.cache import TTLCache


def _big_shelter(count):
    shelter = AnimalShelter("testuser", "testpass", client=mongomock.MongoClient())
    shelter.collection.insert_many(
        [{"rec_num": i, "name": f"Dog {i}", "breed": "Beagle", "location_lat": 30.0,
          "location_long": -97.0} for i in range(1, count + 1)])
    return shelter


###########################
# Ranked rescue views
###########################
def test_rescue_view_is_ranked(shelter):
    result = load_table(shelter, TTLCache(), rf.DISASTER, 0, [])
    assert result["error"] == ""
    assert [row["rank"] for row in result["data"]] == [1, 2, 3]
    assert result["columns"][0]["id"] == "rank"
    assert result["page_action"] == "native"
    assert "top 3 of 3" in result["info"]
    assert all("_id" not in row for row in result["data"])


def test_rescue_view_leaves_out_unavailable_dogs(shelter):
    names = [row["name"] for row in load_table(shelter, TTLCache(), rf.MOUNTAIN, 0, [])["data"]]
    assert "Ghost" not in names
    assert "Sarge" in names


def test_rescue_results_come_from_the_cache_the_second_time(shelter):
    cache = TTLCache()
    load_table(shelter, cache, rf.WATER, 0, [])
    shelter.collection = MagicMock()   # any database call would now fail
    result = load_table(shelter, cache, rf.WATER, 0, [])
    assert [row["name"] for row in result["data"]] == ["Daisy"]
    shelter.collection.find.assert_not_called()


###########################
# Paged Reset view
###########################
def test_reset_shows_first_page(shelter):
    result = load_table(shelter, TTLCache(), rf.RESET, 0, [])
    assert result["page_action"] == "custom"
    assert result["page_count"] == 1
    assert len(result["data"]) == 7
    assert "7 animals" in result["info"]


def test_reset_pages_through_large_collection():
    shelter = _big_shelter(35)
    cache, cursors, seen = TTLCache(), [], []
    for page in range(4):
        result = load_table(shelter, cache, rf.RESET, page, cursors)
        cursors = result["cursors"]
        seen.extend(row["rec_num"] for row in result["data"])
    assert result["page_count"] == 4
    assert seen == list(range(1, 36))


def test_reset_can_go_back_a_page():
    shelter = _big_shelter(25)
    cache = TTLCache()
    first = load_table(shelter, cache, rf.RESET, 0, [])
    second = load_table(shelter, cache, rf.RESET, 1, first["cursors"])
    back = load_table(shelter, cache, rf.RESET, 0, second["cursors"])
    assert back["data"] == first["data"]


def test_reset_jump_to_last_page_walks_forward():
    shelter = _big_shelter(25)
    result = load_table(shelter, TTLCache(), rf.RESET, 2, [])
    assert [row["rec_num"] for row in result["data"]] == list(range(21, 26))
    assert len(result["cursors"]) == 2


def test_reset_page_past_the_end_shows_last_page():
    shelter = _big_shelter(15)
    result = load_table(shelter, TTLCache(), rf.RESET, 99, [])
    assert result["page_current"] == 1
    assert [row["rec_num"] for row in result["data"]] == list(range(11, 16))


def test_get_page_only_reads_one_page_at_a_time():
    shelter = _big_shelter(50)
    rows, _ = get_page(shelter, TTLCache(), 0, [])
    assert len(rows) == TABLE_PAGE_SIZE


###########################
# Errors
###########################
def test_unknown_rescue_type_shows_message(shelter):
    result = load_table(shelter, TTLCache(), "Fire", 0, [])
    assert result["data"] == []
    assert "isn't recognized" in result["error"]


def test_database_failure_shows_message(mock_client):
    shelter = AnimalShelter("testuser", "testpass", client=mock_client)
    shelter.collection = MagicMock()
    shelter.collection.find.side_effect = PyMongoError("connection lost")
    shelter.collection.count_documents.side_effect = PyMongoError("connection lost")
    for rescue_type in (rf.WATER, rf.RESET):
        result = load_table(shelter, TTLCache(), rescue_type, 0, [])
        assert result["data"] == []
        assert "couldn't be reached" in result["error"]


###########################
# Chart, map and highlight
###########################
def test_reset_chart_counts_all_records(shelter):
    figure = load_breed_chart(shelter, TTLCache(), rf.RESET)[0].figure
    assert figure.layout.title.text == ALL_RECORDS_CHART_TITLE
    assert sum(figure.data[0]["values"]) == 7


def test_rescue_chart_counts_every_candidate(shelter):
    figure = load_breed_chart(shelter, TTLCache(), rf.DISASTER)[0].figure
    assert "3 Candidates" in figure.layout.title.text
    assert sum(figure.data[0]["values"]) == 3


def test_chart_with_unknown_type():
    assert load_breed_chart(MagicMock(), TTLCache(), "Fire")[0].children == "No data to display"


def test_map_uses_selected_row():
    rows = [{"location_lat": 1, "location_long": 2}, {"location_lat": 3, "location_long": 4}]
    marker = build_map(rows, [1])[0].children[1]
    assert marker.position == [3, 4]


def test_map_falls_back_to_first_row_when_selection_is_out_of_range():
    rows = [{"location_lat": 1, "location_long": 2}]
    assert build_map(rows, [7])[0].children[1].position == [1, 2]
    assert build_map(rows, [-3])[0].children[1].position == [1, 2]


def test_map_with_no_data():
    assert build_map([], [0])[0].children == "No data available"


def test_map_with_missing_location_field():
    assert build_map([{"breed": "Rottweiler"}], [0])[0].children == "Map data not available"


def test_row_highlight():
    assert build_row_highlight([2]) == [{"if": {"row_index": 2}, "background_color": "#D2F3FF"}]
    assert build_row_highlight([]) == []


###########################
# App startup
###########################
def _component_ids(component):
    # Walk the layout tree and collect every id
    ids = set()
    if getattr(component, "id", None):
        ids.add(component.id)
    children = getattr(component, "children", None)
    if isinstance(children, list):
        for child in children:
            ids |= _component_ids(child)
    elif children is not None and hasattr(children, "children"):
        ids |= _component_ids(children)
    return ids


def test_app_builds_dashboard_when_database_is_up(shelter):
    app = create_app(shelter)
    assert {"filter-type", "status-message", "info-message", "page-cursors",
            "datatable-id", "graph-id", "map-id"} <= _component_ids(app.layout)


def test_app_shows_unavailable_page_when_database_is_down():
    client = MagicMock()
    client.admin.command.side_effect = ServerSelectionTimeoutError("no server")
    app = create_app(AnimalShelter("testuser", "testpass", client=client))
    assert "datatable-id" not in _component_ids(app.layout)
    assert "Database unavailable" in str(app.layout)
