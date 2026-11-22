# Becca Hammond
# CS499 Enhancement Two - Algorithms and Data Structures
# 11/16/2026
# Version 2.0
# Version 1.0 (11/15/2026): Enhancement One, Software Design and Engineering
#
# Purpose: Dash callbacks for the dashboard (the controller). Each callback is
# a thin wrapper around a plain function, so the logic can be tested without
# a browser or a running server.
#
# Changes in Version 2.0, with costs for n animals in the collection, m
# matching candidates, k ranked results, b distinct breeds and a page size s:
#
#   Reset view
#     Before: loaded all n records into a DataFrame and sent all of them to
#             the browser. O(n) time and memory on every click.
#     Now:    keyset pagination loads one page at a time. O(log n + s) per
#             page and O(s) memory.
#
#   Rescue views
#     Before: returned every match unranked, in no particular order.
#     Now:    one pass over the matches ranks them with a min-heap and counts
#             breeds for the chart at the same time. O(m log k) time,
#             O(k + b) memory.
#
#   Breed chart
#     Before: rebuilt a DataFrame from every row and ran value_counts() each
#             time the table changed.
#     Now:    computed once per filter and cached. Top 10 picked with
#             heapq.nlargest in O(b log 10).
#
#   Map
#     Before: rebuilt a DataFrame from every row to read one row. O(n).
#     Now:    reads the selected row directly from the list. O(1).
#
#   Repeat clicks
#     Results, page counts and pages are kept in a TTL cache, so clicking the
#     same filter again within a minute skips the database. O(1) lookup.

import logging
import math
from typing import Dict, List, Optional, Tuple

import dash_leaflet as dl
import plotly.express as px
from dash import Dash, Input, Output, State, ctx, dcc, html

from grazioso.data.animal_shelter import AnimalShelter
from grazioso.exceptions import DatabaseError, UnknownRescueTypeError
from grazioso.layout import (FILTER_ID, GRAPH_ID, INFO_ID, MAP_ID, PAGE_STORE_ID,
                             STATUS_ID, TABLE_ID, TABLE_PAGE_SIZE, table_columns)
from grazioso.services import rescue_filters
from grazioso.services.cache import TTLCache
from grazioso.services.ranking import DEFAULT_TOP_K, RankingResult, rank_candidates, top_breeds

logger = logging.getLogger(__name__)

###########################
# Chart and map settings
###########################
TOP_BREED_COUNT = 10
ALL_RECORDS_CHART_TITLE = f"Top {TOP_BREED_COUNT} Breeds in All Records"
# Austin, TX, where the Austin Animal Center data comes from
MAP_CENTER = [30.75, -97.48]
MAP_ZOOM = 10
MAP_STYLE = {"width": "100%", "height": "500px"}
# Leave the ObjectId out of query results. The data table can't display it.
NO_ID_PROJECTION = {"_id": 0}
# The chart only needs the breed, so the database sends nothing else
BREED_ONLY_PROJECTION = {"breed": 1, "_id": 0}

UNKNOWN_TYPE_MESSAGE = "That rescue type isn't recognized. Pick one of the options above."
DATABASE_MESSAGE = "The database couldn't be reached. Try again in a moment."


###########################
# Ranked rescue results
###########################
def get_ranking(shelter: AnimalShelter, cache: TTLCache, rescue_type: str) -> RankingResult:
    """
    Rank the candidates for a rescue type, using the cache when possible.
    Candidates are streamed from the cursor straight into the heap, so they
    are never all held in memory at once. O(m log k) on a cache miss, O(1) on
    a hit.
    """
    profile = rescue_filters.get_profile(rescue_type)

    def compute() -> RankingResult:
        query = rescue_filters.get_query(rescue_type)
        return rank_candidates(shelter.iterate(query, NO_ID_PROJECTION), profile, DEFAULT_TOP_K)

    return cache.get_or_compute(("rank", rescue_type), compute)


###########################
# Paged Reset results
###########################
def get_page(shelter: AnimalShelter, cache: TTLCache, page: int,
             cursors: List[str]) -> Tuple[List[dict], List[str]]:
    """
    Return one page of every animal, plus the updated list of page cursors.

    cursors[i] is the last _id on page i (as a string, so the browser can
    store it). Page p starts right after cursors[p - 1].

    Moving to the next or previous page is one keyset query, O(log n + s).
    Jumping ahead to a page the browser hasn't seen yet walks forward one
    page at a time from the last known cursor. That is the trade-off of
    keyset pagination: it is fast for next and previous, slower for a big
    jump.
    """
    cursors = list(cursors or [])

    def fetch(after_id: Optional[str]):
        def compute():
            documents, last_id = shelter.read_page({}, after_id, TABLE_PAGE_SIZE)
            return documents, (str(last_id) if last_id is not None else None)
        return cache.get_or_compute(("page", after_id), compute)

    # Walk forward to fill in any cursors the browser doesn't have yet
    while len(cursors) < page:
        after_id = cursors[-1] if cursors else None
        _documents, last_id = fetch(after_id)
        if last_id is None:
            break
        cursors.append(last_id)

    # If the walk ran out of pages early, show the last page it reached
    page = min(page, len(cursors))
    after_id = None if page == 0 else cursors[page - 1]
    documents, last_id = fetch(after_id)
    if last_id is not None and len(cursors) == page:
        cursors.append(last_id)

    # Copy each row without _id. The cached documents are left untouched.
    rows = [{key: value for key, value in document.items() if key != "_id"}
            for document in documents]
    return rows, cursors


def get_total(shelter: AnimalShelter, cache: TTLCache) -> int:
    """ Number of animals in the collection, cached """
    return cache.get_or_compute(("count", "all"), lambda: shelter.count({}))


###########################
# Main table callback logic
###########################
def load_table(shelter: AnimalShelter, cache: TTLCache, rescue_type: str,
               page: int, cursors: List[str]) -> Dict:
    """
    Everything the data table needs for one filter and page.
    Returns a dict of component properties, so the callback and the tests
    read the same values.
    """
    result = {
        "data": [], "columns": table_columns(ranked=False), "page_action": "custom",
        "sort_action": "none", "filter_action": "none", "page_count": 1,
        "page_current": 0, "cursors": [], "error": "", "info": "",
    }

    try:
        if rescue_type == rescue_filters.RESET:
            total = get_total(shelter, cache)
            page_count = max(1, math.ceil(total / TABLE_PAGE_SIZE))
            page = min(max(page or 0, 0), page_count - 1)
            rows, cursors = get_page(shelter, cache, page, cursors)
            result.update(data=rows, page_count=page_count, page_current=page, cursors=cursors,
                          info=f"Showing page {page + 1} of {page_count:,} ({total:,} animals). "
                               f"Pages load {TABLE_PAGE_SIZE} records at a time.")
            return result

        ranking = get_ranking(shelter, cache, rescue_type)
    except UnknownRescueTypeError as error:
        logger.warning("%s", error)
        result["error"] = UNKNOWN_TYPE_MESSAGE
        return result
    except DatabaseError:
        # The error and its cause were already logged by the CRUD module
        result["error"] = DATABASE_MESSAGE
        return result

    # Ranked results are at most k rows, so sorting and filtering them in the
    # browser is cheap again
    result.update(data=ranking.top, columns=table_columns(ranked=True), page_action="native",
                  sort_action="native", filter_action="native", page_count=None,
                  info=f"Showing the top {len(ranking.top)} of {ranking.total} available "
                       f"candidates, ranked by suitability score.")
    logger.info("Rescue type %s: %d candidates, top %d shown",
                rescue_type, ranking.total, len(ranking.top))
    return result


def load_breed_chart(shelter: AnimalShelter, cache: TTLCache, rescue_type: str):
    """ Pie chart of the most common breeds for the current filter """
    try:
        if rescue_type == rescue_filters.RESET:
            # One streaming pass over only the breed field, then the top 10.
            # O(n) the first time, cached after that.
            breeds = cache.get_or_compute(
                ("breeds", "all"),
                lambda: top_breeds((doc.get("breed", "Unknown")
                                    for doc in shelter.iterate({}, BREED_ONLY_PROJECTION)),
                                   TOP_BREED_COUNT))
            title = ALL_RECORDS_CHART_TITLE
        else:
            ranking = get_ranking(shelter, cache, rescue_type)
            breeds = top_breeds(ranking.breed_counts.elements(), TOP_BREED_COUNT)
            title = f"Breeds Among All {ranking.total} Candidates"
    except (UnknownRescueTypeError, DatabaseError):
        return [html.Div("No data to display")]

    if not breeds:
        return [html.Div("No data to display")]

    names = [name for name, _count in breeds]
    counts = [count for _name, count in breeds]
    return [dcc.Graph(figure=px.pie(values=counts, names=names, title=title, hole=0.3))]


def build_map(view_data: Optional[List[dict]], selected_rows: Optional[List[int]]):
    """
    Map with a marker for the selected animal.
    Reads the one selected row straight from the list, O(1). Version 1.0
    built a DataFrame from every row to do this.
    """
    if not view_data:
        return [html.Div("No data available")]

    row = selected_rows[0] if selected_rows else 0
    # The selection can point past the end of the data after a new filter
    if not 0 <= row < len(view_data):
        row = 0
    animal = view_data[row]

    try:
        lat = animal["location_lat"]
        lon = animal["location_long"]
    except KeyError as error:
        logger.error("Map data missing field %s", error)
        return [html.Div("Map data not available")]

    return [
        dl.Map(style=MAP_STYLE, center=MAP_CENTER, zoom=MAP_ZOOM, children=[
            dl.TileLayer(id="base-layer-id"),
            # Marker with a tooltip for the breed and a popup for the name
            dl.Marker(position=[lat, lon], children=[
                dl.Tooltip(animal.get("breed", "")),
                dl.Popup([
                    html.H1("Animal Name"),
                    html.P(animal.get("name", "")),
                ]),
            ]),
        ])
    ]


def build_row_highlight(selected_rows: Optional[List[int]]) -> List[dict]:
    """ Highlight the selected row in the data table """
    if not selected_rows:
        return []
    return [{"if": {"row_index": i}, "background_color": "#D2F3FF"} for i in selected_rows]


#############################################
# Interaction Between Components / Controller
#############################################
def register_callbacks(app: Dash, shelter: AnimalShelter,
                       cache: Optional[TTLCache] = None) -> TTLCache:
    """ Connect the layout's components to the functions above """
    cache = cache or TTLCache()

    @app.callback(Output(TABLE_ID, "data"),
                  Output(TABLE_ID, "columns"),
                  Output(TABLE_ID, "page_action"),
                  Output(TABLE_ID, "sort_action"),
                  Output(TABLE_ID, "filter_action"),
                  Output(TABLE_ID, "page_count"),
                  Output(TABLE_ID, "page_current"),
                  Output(PAGE_STORE_ID, "data"),
                  Output(STATUS_ID, "children"),
                  Output(INFO_ID, "children"),
                  Input(FILTER_ID, "value"),
                  Input(TABLE_ID, "page_current"),
                  State(PAGE_STORE_ID, "data"))
    def update_dashboard(filter_type, page_current, cursors):
        # A new filter starts back on the first page with no saved cursors
        if ctx.triggered_id == FILTER_ID:
            page_current, cursors = 0, []
        result = load_table(shelter, cache, filter_type, page_current or 0, cursors)
        return (result["data"], result["columns"], result["page_action"],
                result["sort_action"], result["filter_action"], result["page_count"],
                result["page_current"], result["cursors"], result["error"], result["info"])

    @app.callback(Output(GRAPH_ID, "children"),
                  Input(FILTER_ID, "value"))
    def update_graphs(filter_type):
        return load_breed_chart(shelter, cache, filter_type)

    @app.callback(Output(TABLE_ID, "style_data_conditional"),
                  Input(TABLE_ID, "selected_rows"))
    def update_styles(selected_rows):
        return build_row_highlight(selected_rows)

    @app.callback(Output(MAP_ID, "children"),
                  Input(TABLE_ID, "derived_virtual_data"),
                  Input(TABLE_ID, "derived_virtual_selected_rows"))
    def update_map(view_data, selected_rows):
        return build_map(view_data, selected_rows)

    return cache
