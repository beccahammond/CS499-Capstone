# Becca Hammond
# CS499 Enhancement One - Software Design and Engineering
# 11/15/2026
# Version 1.0
#
# Purpose: Tests for the callback logic and the app startup. The callbacks
# call plain functions, so they can be tested here without a browser.

from unittest.mock import MagicMock

from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from app import create_app
from grazioso.callbacks import (CHART_TITLE, build_breed_chart, build_map,
                                build_row_highlight, load_table_data)
from grazioso.data.animal_shelter import AnimalShelter
from grazioso.services import rescue_filters as rf


###########################
# Loading table data
###########################
def test_load_table_data_returns_records_without_id(shelter):
    records, message = load_table_data(shelter, rf.WATER)
    assert message == ""
    assert [r["name"] for r in records] == ["Daisy"]
    assert "_id" not in records[0]


def test_load_table_data_reset_returns_everything(shelter):
    records, message = load_table_data(shelter, rf.RESET)
    assert len(records) == 5
    assert message == ""


def test_unknown_rescue_type_shows_message(shelter):
    records, message = load_table_data(shelter, "Fire")
    assert records == []
    assert "isn't recognized" in message


def test_database_failure_shows_message(mock_client):
    shelter = AnimalShelter("testuser", "testpass", client=mock_client)
    shelter.collection = MagicMock()
    shelter.collection.find.side_effect = PyMongoError("connection lost")
    records, message = load_table_data(shelter, rf.WATER)
    assert records == []
    assert "couldn't be reached" in message


###########################
# Chart, map and highlight
###########################
def test_chart_with_no_data():
    assert build_breed_chart([])[0].children == "No data to display"


def test_chart_title_describes_the_results(shelter):
    records, _ = load_table_data(shelter, rf.RESET)
    figure = build_breed_chart(records)[0].figure
    assert figure.layout.title.text == CHART_TITLE


def test_map_uses_selected_row(shelter):
    records, _ = load_table_data(shelter, rf.RESET)
    marker = build_map(records, [1])[0].children[1]
    assert marker.position == [records[1]["location_lat"], records[1]["location_long"]]


def test_map_falls_back_to_first_row_when_selection_is_out_of_range(shelter):
    records, _ = load_table_data(shelter, rf.WATER)
    marker = build_map(records, [7])[0].children[1]
    assert marker.position == [records[0]["location_lat"], records[0]["location_long"]]


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
    assert {"filter-type", "status-message", "datatable-id", "graph-id", "map-id"} <= _component_ids(app.layout)


def test_app_shows_unavailable_page_when_database_is_down():
    client = MagicMock()
    client.admin.command.side_effect = ServerSelectionTimeoutError("no server")
    app = create_app(AnimalShelter("testuser", "testpass", client=client))
    assert "datatable-id" not in _component_ids(app.layout)
    assert "Database unavailable" in str(app.layout)
