# Becca Hammond
# CS499 Enhancement Two - Algorithms and Data Structures
# 11/16/2026
# Version 2.0
# Version 1.0 (11/15/2026): Enhancement One, Software Design and Engineering
#
# Purpose: Builds the dashboard's page layout (the view). The layout used to
# sit in the same notebook cell as the database login, the queries and the
# callbacks. Now it only describes what goes on the page.
#
# Changes in Version 2.0:
#   - Rank and suitability score columns for the ranked rescue results
#   - A Store that remembers where each page ends, for keyset pagination
#   - A separate line for normal status messages, so errors stand out

import logging
from pathlib import Path
from typing import Optional

from dash import dash_table, dcc, html

from grazioso.services.rescue_filters import RESCUE_TYPE_OPTIONS, RESET

logger = logging.getLogger(__name__)

###########################
# Page settings
###########################
PAGE_TITLE = "CS-499 Dashboard - Grazioso Salvare - Becca Hammond"
LOGO_FILENAME = "Grazioso Salvare Logo.png"
LOGO_LINK = "https://www.snhu.edu"
TABLE_PAGE_SIZE = 10

# Columns shown in the data table, in order. Listing them here means the app
# doesn't have to load the whole collection at startup to find them.
TABLE_COLUMNS = [
    "rec_num", "age_upon_outcome", "animal_id", "animal_type", "breed", "color",
    "date_of_birth", "datetime", "monthyear", "name", "outcome_subtype",
    "outcome_type", "sex_upon_outcome", "location_lat", "location_long",
    "age_upon_outcome_in_weeks",
]

# Extra columns shown first when results are ranked
RANK_COLUMNS = ["rank", "suitability_score"]

# Component ids shared with callbacks.py
FILTER_ID = "filter-type"
STATUS_ID = "status-message"
INFO_ID = "info-message"
PAGE_STORE_ID = "page-cursors"
TABLE_ID = "datatable-id"
GRAPH_ID = "graph-id"
MAP_ID = "map-id"

###########################
# Styles
###########################
LOGO_STYLE = {"height": "150px"}
FILTER_BOX_STYLE = {"margin": "20px", "padding": "20px", "border": "2px solid #cccccc",
                    "borderRadius": "5px", "backgroundColor": "#fafafa"}
FILTER_LABEL_STYLE = {"fontWeight": "bold", "fontSize": "18px", "marginBottom": "10px"}
STATUS_STYLE = {"margin": "0 20px", "color": "#b00020", "fontWeight": "bold"}
INFO_STYLE = {"margin": "0 20px", "fontStyle": "italic"}
CELL_STYLE = {"textAlign": "left", "padding": "5px", "minWidth": "100px"}
HEADER_STYLE = {"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"}
CHART_STYLE = {"flex": "1", "minWidth": "0"}
MAP_STYLE = {"flex": "1", "minWidth": "0", "height": "500px"}


def logo_exists(assets_folder: str) -> bool:
    # The original opened the logo file without checking that it was there,
    # so a missing file crashed the whole dashboard. Now it logs a warning
    # and the page loads without the logo.
    path = Path(assets_folder) / LOGO_FILENAME
    if not path.is_file():
        logger.warning("Logo not found at %s, loading the page without it", path)
        return False
    return True


def table_columns(ranked: bool) -> list:
    """ Column definitions for the data table, with rank columns when ranked """
    names = (RANK_COLUMNS if ranked else []) + TABLE_COLUMNS
    return [{"name": name, "id": name, "deletable": False, "selectable": True} for name in names]


def build_layout(logo_src: Optional[str] = None) -> html.Div:
    """
    Build the main dashboard page.
    logo_src is the URL of the logo, or None to leave it out.
    The table starts empty. The filter callback fills it on page load.
    """
    header = [html.Center(html.B(html.H1(PAGE_TITLE)))]
    if logo_src:
        header.append(html.Center(html.A(
            html.Img(src=logo_src, style=LOGO_STYLE, alt="Grazioso Salvare logo"),
            href=LOGO_LINK,
            target="_blank",
        )))

    return html.Div(header + [
        html.Hr(),
        # Interactive Filter Options
        html.Div([
            html.Label("Filter by Rescue Type:", style=FILTER_LABEL_STYLE),
            dcc.RadioItems(
                id=FILTER_ID,
                options=[{"label": label, "value": value} for label, value in RESCUE_TYPE_OPTIONS],
                value=RESET,
                labelStyle={"display": "block", "marginTop": "10px"},
                style={"fontSize": "16px"},
            ),
        ], style=FILTER_BOX_STYLE),
        # Shows an error message when a query fails. Empty the rest of the time.
        html.Div(id=STATUS_ID, role="alert", style=STATUS_STYLE),
        # Normal status, like which page is showing or how many candidates matched
        html.Div(id=INFO_ID, role="status", style=INFO_STYLE),
        # Last _id of each page the browser has loaded, for keyset pagination.
        # Kept in the browser so each user pages independently.
        dcc.Store(id=PAGE_STORE_ID, data=[]),
        html.Hr(),
        dash_table.DataTable(
            id=TABLE_ID,
            columns=table_columns(ranked=False),
            data=[],
            row_selectable="single",
            selected_rows=[0],
            page_size=TABLE_PAGE_SIZE,
            page_current=0,
            # The callbacks switch these between server-side paging for
            # Reset and in-browser sorting and filtering for ranked results
            sort_action="none",
            filter_action="none",
            page_action="custom",
            style_table={"overflowX": "auto"},
            style_cell=CELL_STYLE,
            style_header=HEADER_STYLE,
        ),
        html.Br(),
        html.Hr(),
        # Chart and map side by side
        html.Div(style={"display": "flex", "gap": "20px"}, children=[
            html.Div(id=GRAPH_ID, style=CHART_STYLE),
            html.Div(id=MAP_ID, style=MAP_STYLE),
        ]),
    ])


def build_unavailable_layout(message: str) -> html.Div:
    """ Page shown when the database can't be reached at startup """
    return html.Div([
        html.Center(html.B(html.H1(PAGE_TITLE))),
        html.Hr(),
        html.Div([
            html.H2("Database unavailable"),
            html.P(message),
            html.P("Check that MongoDB is running and that the settings in your .env file "
                   "are correct, then restart the dashboard."),
        ], role="alert", style=FILTER_BOX_STYLE),
    ])
