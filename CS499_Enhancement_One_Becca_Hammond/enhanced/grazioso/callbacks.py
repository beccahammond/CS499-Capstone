# Becca Hammond
# CS499 Enhancement One - Software Design and Engineering
# 11/15/2026
# Version 1.0
#
# Purpose: Dash callbacks for the dashboard (the controller). Each callback is
# a thin wrapper around a plain function, so the logic can be tested without
# a browser or a running server.

import logging
from typing import List, Optional, Tuple

import dash_leaflet as dl
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dcc, html

from grazioso.data.animal_shelter import AnimalShelter
from grazioso.exceptions import DatabaseError, UnknownRescueTypeError
from grazioso.layout import FILTER_ID, GRAPH_ID, MAP_ID, STATUS_ID, TABLE_ID
from grazioso.services import rescue_filters

logger = logging.getLogger(__name__)

###########################
# Chart and map settings
###########################
TOP_BREED_COUNT = 10
CHART_TITLE = f"Top {TOP_BREED_COUNT} Breeds in Current Results"
# Austin, TX, where the Austin Animal Center data comes from
MAP_CENTER = [30.75, -97.48]
MAP_ZOOM = 10
MAP_STYLE = {"width": "100%", "height": "500px"}
# Leave the ObjectId out of query results. The data table can't display it.
NO_ID_PROJECTION = {"_id": 0}


def load_table_data(shelter: AnimalShelter, rescue_type: str) -> Tuple[List[dict], str]:
    """
    Run the query for a rescue type.
    Returns (records, message). message is empty when everything worked,
    and explains the problem when it didn't.
    """
    try:
        query = rescue_filters.get_query(rescue_type)
    except UnknownRescueTypeError as error:
        logger.warning("%s", error)
        return [], "That rescue type isn't recognized. Pick one of the options above."

    try:
        records = shelter.read(query, NO_ID_PROJECTION)
    except DatabaseError:
        # The error and its cause were already logged by the CRUD module
        return [], "The database couldn't be reached. Try again in a moment."

    logger.info("Rescue type %s returned %d records", rescue_type, len(records))
    return records, ""


def build_breed_chart(view_data: Optional[List[dict]]):
    """ Pie chart of the most common breeds in the table's current rows """
    if not view_data:
        return [html.Div("No data to display")]

    breed_counts = pd.DataFrame.from_dict(view_data)["breed"].value_counts().head(TOP_BREED_COUNT)
    return [
        dcc.Graph(
            figure=px.pie(
                values=breed_counts.values,
                names=breed_counts.index,
                title=CHART_TITLE,
                hole=0.3,
            )
        )
    ]


def build_map(view_data: Optional[List[dict]], selected_rows: Optional[List[int]]):
    """
    Map with a marker for the selected animal.
    view_data is every row in the table after sorting and filtering.
    selected_rows is a list of selected row numbers. The table only allows
    one selection, so only the first entry is used.
    """
    if not view_data:
        return [html.Div("No data available")]

    df = pd.DataFrame.from_dict(view_data)
    row = selected_rows[0] if selected_rows else 0
    # The selection can point past the end of the data after a new filter
    if row >= len(df):
        row = 0

    try:
        lat = df.loc[row, "location_lat"]
        lon = df.loc[row, "location_long"]
        breed = df.loc[row, "breed"]
        name = df.loc[row, "name"]
    except KeyError as error:
        logger.error("Map data missing field %s", error)
        return [html.Div("Map data not available")]

    return [
        dl.Map(style=MAP_STYLE, center=MAP_CENTER, zoom=MAP_ZOOM, children=[
            dl.TileLayer(id="base-layer-id"),
            # Marker with a tooltip for the breed and a popup for the name
            dl.Marker(position=[lat, lon], children=[
                dl.Tooltip(breed),
                dl.Popup([
                    html.H1("Animal Name"),
                    html.P(name),
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
def register_callbacks(app: Dash, shelter: AnimalShelter) -> None:
    """ Connect the layout's components to the functions above """

    @app.callback(Output(TABLE_ID, "data"),
                  Output(STATUS_ID, "children"),
                  Input(FILTER_ID, "value"))
    def update_dashboard(filter_type):
        return load_table_data(shelter, filter_type)

    @app.callback(Output(GRAPH_ID, "children"),
                  Input(TABLE_ID, "derived_virtual_data"))
    def update_graphs(view_data):
        return build_breed_chart(view_data)

    @app.callback(Output(TABLE_ID, "style_data_conditional"),
                  Input(TABLE_ID, "selected_rows"))
    def update_styles(selected_rows):
        return build_row_highlight(selected_rows)

    @app.callback(Output(MAP_ID, "children"),
                  Input(TABLE_ID, "derived_virtual_data"),
                  Input(TABLE_ID, "derived_virtual_selected_rows"))
    def update_map(view_data, selected_rows):
        return build_map(view_data, selected_rows)
