"""
Module for generating various plots and visualizations of PyPSA networks.

This module provides functions for creating both static and interactive
representations of electrical grids, including geographical plots,
and visualizations incorporating simulation results.
"""

import logging
import os
from typing import Callable, Optional

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import pandas as pd
import pypsa


def get_line_colors_by_voltage(n: pypsa.Network) -> pd.Series:
    """
    Calculates line colors based on the nominal voltage level of the connected buses.

    Args:
        n (pypsa.Network): The PyPSA network.

    Returns:
        pd.Series: A pandas Series with line names as index and corresponding colors as values.
                   Returns an empty Series if an error occurs.
    """
    try:
        line_colors_by_voltage = pd.Series(index=n.lines.index, dtype=str)

        for line_name, line in n.lines.iterrows():
            bus0_name = line.bus0
            bus0_v_nom = n.buses.loc[bus0_name, 'v_nom']

            if bus0_v_nom < 300:
                line_colors_by_voltage.loc[line_name] = 'green'
            else:
                line_colors_by_voltage.loc[line_name] = 'red'

        return line_colors_by_voltage

    except Exception as e:
        logging.error(f"Error calculating line colors by voltage: {e}")
        return pd.Series(dtype=str)


def get_line_colors_under_construction(n: pypsa.Network) -> pd.Series:
    """
    Calculates line colors based on whether the line is under construction.

    Args:
        n (pypsa.Network): The PyPSA network.

    Returns:
        pd.Series: A pandas Series with line names as index and corresponding colors as values.
                   Returns an empty Series if an error occurs.
    """
    try:
        line_colors_under_construction = pd.Series(index=n.lines.index, dtype=str)

        for line_name, line in n.lines.iterrows():
            if line.get('under_construction', False):  # Safely get attribute, default to False
                line_colors_under_construction.loc[line_name] = 'red'
            else:
                line_colors_under_construction.loc[line_name] = 'black'

        return line_colors_under_construction

    except Exception as e:
        logging.error(f"Error calculating line colors by construction status: {e}")
        return pd.Series(dtype=str)


def get_line_colors_by_extendable(n: pypsa.Network) -> pd.Series:
    """
    Calculates line colors based on whether the line is extendable (s_nom_extendable).

    Args:
        n (pypsa.Network): The PyPSA network.

    Returns:
        pd.Series: A pandas Series with line names as index and corresponding colors as values.
                   Returns an empty Series if an error occurs.
    """
    try:
        line_colors = pd.Series('black', index=n.lines.index, dtype=str)

        if 's_nom_extendable' in n.lines.columns:
            line_colors.loc[n.lines['s_nom_extendable']] = 'red'

        return line_colors

    except Exception as e:
        logging.error(f"Error calculating line colors by extendable status: {e}")
        return pd.Series(dtype=str)


def get_line_colors_by_congestion(n: pypsa.Network) -> pd.Series:
    """
    Calculates line colors based on whether the power flow in a line is at or near its maximum capacity.

    Args:
        n (pypsa.Network): The PyPSA network.

    Returns:
        pd.Series: A pandas Series with line names as index and corresponding colors as values.
                   Returns an empty Series if an error occurs.
    """
    try:
        line_colors = pd.Series('black', index=n.lines.index, dtype=str)  # Default to black

        if n.lines_t.p0.empty:
            logging.warning("No time-dependent line data (n.lines_t.p0) found. All lines will be black.")
            return line_colors

        # Filter for lines that actually have power flow data
        lines_with_flow_data = n.lines.index.intersection(n.lines_t.p0.columns)
        if lines_with_flow_data.empty:
            logging.warning("No power flow data found for any line in n.lines_t.p0. All lines will be black.")
            return line_colors

        # Select relevant parts of the network components
        relevant_lines = n.lines.loc[lines_with_flow_data]
        relevant_p0 = n.lines_t.p0[lines_with_flow_data]

        # Calculate the absolute maximum allowed apparent power for each relevant line
        # s_max = s_nom * s_max_pu. Default s_max_pu to 1.0 if not present.
        s_max_abs = relevant_lines['s_nom'] * relevant_lines.get('s_max_pu', 1.0)

        # Calculate maximum absolute flow over all timesteps for each line
        max_abs_flow_per_line = relevant_p0.abs().max(axis=0)

        # Determine which lines are congested (flow >= 95% of max_s)
        congested_lines_mask = (max_abs_flow_per_line >= 0.95 * s_max_abs)

        # Update colors for congested lines
        line_colors.loc[congested_lines_mask[congested_lines_mask].index] = 'red'

        return line_colors

    except Exception as e:
        logging.error(f"Error calculating line colors by congestion: {e}")
        return pd.Series(dtype=str)


def get_line_colors_by_expansion(n: pypsa.Network) -> pd.Series:
    """
    Calculates line colors based on whether the line capacity was expanded (s_nom_opt > s_nom).

    Args:
        n (pypsa.Network): The solved PyPSA network.

    Returns:
        pd.Series: A pandas Series with line names as index and corresponding colors as values.
                   Expanded lines are red, others are black.
    """
    try:
        line_colors = pd.Series('black', index=n.lines.index, dtype=str)

        if 's_nom_opt' in n.lines.columns:
            # Check for expansion with a small tolerance for float precision
            expanded_mask = (n.lines['s_nom_opt'] > n.lines['s_nom'] + 1e-3)
            line_colors.loc[expanded_mask] = 'red'

        return line_colors

    except Exception as e:
        logging.error(f"Error calculating line colors by expansion: {e}")
        return pd.Series(dtype=str)


def get_transformer_colors_by_expansion(n: pypsa.Network) -> pd.Series:
    """
    Calculates transformer colors based on whether the capacity was expanded (s_nom_opt > s_nom).

    Args:
        n (pypsa.Network): The solved PyPSA network.

    Returns:
        pd.Series: A pandas Series with transformer names as index and corresponding colors as values.
                   Expanded transformers are purple, others are black.
    """
    try:
        trafo_colors = pd.Series('black', index=n.transformers.index, dtype=str)

        if 's_nom_opt' in n.transformers.columns:
            # Check for expansion with a small tolerance for float precision
            expanded_mask = (n.transformers['s_nom_opt'] > n.transformers['s_nom'] + 1e-3)
            trafo_colors.loc[expanded_mask] = 'purple'

        return trafo_colors

    except Exception as e:
        logging.error(f"Error calculating transformer colors by expansion: {e}")
        return pd.Series(dtype=str)


def get_transformer_widths_by_expansion(n: pypsa.Network, scale: float = 0.01, min_width: float = 3.0) -> pd.Series:
    """
    Calculates transformer widths based on the amount of capacity expansion (s_nom_opt - s_nom).

    Args:
        n (pypsa.Network): The solved PyPSA network.
        scale (float): Scaling factor for the expansion amount.
        min_width (float): Minimum width for all transformers.

    Returns:
        pd.Series: A pandas Series with transformer names as index and corresponding widths as values.
    """
    try:
        widths = pd.Series(min_width, index=n.transformers.index)

        if 's_nom_opt' in n.transformers.columns:
            expansion = (n.transformers['s_nom_opt'] - n.transformers['s_nom']).clip(lower=0)
            widths += expansion * scale

        return widths

    except Exception as e:
        logging.error(f"Error calculating transformer widths by expansion: {e}")
        return pd.Series(min_width, index=n.transformers.index)


def get_line_widths_by_expansion(n: pypsa.Network, scale: float = 0.01, min_width: float = 1.5) -> pd.Series:
    """
    Calculates line widths based on the amount of capacity expansion (s_nom_opt - s_nom).

    Args:
        n (pypsa.Network): The solved PyPSA network.
        scale (float): Scaling factor for the expansion amount.
        min_width (float): Minimum width for all lines.

    Returns:
        pd.Series: A pandas Series with line names as index and corresponding widths as values.
    """
    try:
        widths = pd.Series(min_width, index=n.lines.index)

        if 's_nom_opt' in n.lines.columns:
            expansion = (n.lines['s_nom_opt'] - n.lines['s_nom']).clip(lower=0)
            widths += expansion * scale

        return widths

    except Exception as e:
        logging.error(f"Error calculating line widths by expansion: {e}")
        return pd.Series(min_width, index=n.lines.index)


# ---------------------------------------------------------------------------
# NPAP-style constants (from npap.visualization.PlotConfig defaults)
# ---------------------------------------------------------------------------
NPAP_LINE_HIGH_VOLTAGE_COLOR = "#029E73"   # green – high voltage lines (>300 kV)
NPAP_LINE_LOW_VOLTAGE_COLOR = "#CA9161"    # brown/orange – low voltage lines (<=300 kV)
NPAP_TRAFO_COLOR = "#ECE133"              # yellow – transformers
NPAP_DC_LINK_COLOR = "#CC78BC"            # pink/purple – DC links
NPAP_NODE_COLOR = "#0173B2"               # blue – buses
NPAP_LINE_INVESTMENT_COLOR = "#D55E00"    # orange-red – line investment
NPAP_TRAFO_INVESTMENT_COLOR = "#882255"  # dark magenta – trafo investment
NPAP_VOLTAGE_THRESHOLD = 300.0

NPAP_MAP_STYLE = "carto-positron"
NPAP_BG_COLOR = "#008080"                 # teal background

# For voltage-unaware: a single dark color for all existing lines
NPAP_UNIFORM_LINE_COLOR = "#636363"

# Predefined region view settings: {center_lat, center_lon, zoom}
REGION_VIEWS = {
    'europe': dict(center_lat=52.0, center_lon=14.0, zoom=3.7),
    'adria':  dict(center_lat=42.5, center_lon=15.5, zoom=5.5),
    'sicily': dict(center_lat=37.5, center_lon=14, zoom=8.7),
}


def _get_expansion_mask_lines(n: pypsa.Network):
    """Boolean mask for lines that were expanded."""
    if 's_nom_opt' in n.lines.columns:
        return n.lines['s_nom_opt'] > n.lines['s_nom'] + 1e-3
    return pd.Series(False, index=n.lines.index)


def _get_expansion_mask_trafos(n: pypsa.Network):
    """Boolean mask for transformers that were expanded."""
    if 's_nom_opt' in n.transformers.columns:
        return n.transformers['s_nom_opt'] > n.transformers['s_nom'] + 1e-3
    return pd.Series(False, index=n.transformers.index)


def _expansion_amount(s_nom, s_nom_opt):
    """Return the expansion in MVA (clipped to >= 0)."""
    return max(0.0, s_nom_opt - s_nom)


def _investment_line_width(expansion_mva, max_expansion, min_width=3.5, max_width=12.0):
    """Map expansion MVA to a line width linearly between min_width and max_width."""
    if max_expansion <= 0:
        return min_width
    t = min(expansion_mva / max_expansion, 1.0)
    return min_width + t * (max_width - min_width)



def _build_branch_traces(n: pypsa.Network, voltage_aware: bool,
                         min_line_investment: float = 0.0,
                         min_trafo_investment: float = 0.0):
    """
    Build Plotly Scattermapbox traces for lines, transformers, and links
    using the NPAP visualization style with investment highlighting.

    Investment lines are rendered with per-segment widths proportional to
    the expansion amount. Expanded trafos are rendered as artificially
    extended line segments (~0.15 degrees, north–south) centered on their
    midpoint, with width proportional to expansion.

    Args:
        n: PyPSA network.
        voltage_aware: Whether to color by voltage level.
        min_line_investment: Minimum expansion (MVA) for a line to be shown as investment.
        min_trafo_investment: Minimum expansion (MVA) for a trafo to be shown as investment.
    """
    import numpy as np
    import plotly.graph_objects as go

    expanded_lines = _get_expansion_mask_lines(n)
    expanded_trafos = _get_expansion_mask_trafos(n)

    # Helper to get bus coordinates
    def _bus_coords(bus_name):
        bus = n.buses.loc[bus_name]
        return bus.y, bus.x  # lat, lon

    # ---- Collect non-investment line segments by group ----
    groups = {}

    def _add_segment(key, lat0, lon0, lat1, lon1):
        if key not in groups:
            groups[key] = dict(lats=[], lons=[], count=0)
        g = groups[key]
        g['lats'].extend([lat0, lat1, None])
        g['lons'].extend([lon0, lon1, None])
        g['count'] += 1

    # ---- Collect investment data separately (need per-element widths) ----
    # inv_lines stores (lat0, lon0, lat1, lon1, expansion_mva, color_key)
    # color_key is 'line_high', 'line_low', or 'line_existing' so investment
    # lines keep their original voltage color but are rendered thicker.
    inv_lines = []
    inv_trafos = []  # list of (lat_mid, lon_mid, expansion_mva)

    # --- Lines ---
    for idx, line in n.lines.iterrows():
        try:
            lat0, lon0 = _bus_coords(line.bus0)
            lat1, lon1 = _bus_coords(line.bus1)
        except (KeyError, AttributeError):
            continue

        is_expanded = expanded_lines.get(idx, False)
        s_nom = line.get('s_nom', 0)
        s_nom_opt = line.get('s_nom_opt', s_nom)
        expansion = _expansion_amount(s_nom, s_nom_opt)

        # Determine voltage color key for this line
        if voltage_aware:
            v_nom = n.buses.loc[line.bus0, 'v_nom'] if line.bus0 in n.buses.index else 0
            color_key = 'line_high' if v_nom > NPAP_VOLTAGE_THRESHOLD else 'line_low'
        else:
            color_key = 'line_existing'

        if is_expanded and expansion >= min_line_investment:
            inv_lines.append((lat0, lon0, lat1, lon1, expansion, color_key))
        else:
            _add_segment(color_key, lat0, lon0, lat1, lon1)

    # --- Transformers ---
    if not n.transformers.empty:
        for idx, trafo in n.transformers.iterrows():
            try:
                lat0, lon0 = _bus_coords(trafo.bus0)
                lat1, lon1 = _bus_coords(trafo.bus1)
            except (KeyError, AttributeError):
                continue

            is_expanded = expanded_trafos.get(idx, False)
            s_nom = trafo.get('s_nom', 0)
            s_nom_opt = trafo.get('s_nom_opt', s_nom)
            expansion = _expansion_amount(s_nom, s_nom_opt)

            if is_expanded and expansion >= min_trafo_investment:
                inv_trafos.append((lat0, lon0, lat1, lon1, expansion))
            elif voltage_aware:
                _add_segment('trafo', lat0, lon0, lat1, lon1)
            else:
                _add_segment('line_existing', lat0, lon0, lat1, lon1)

    # --- Links (DC) ---
    if not n.links.empty:
        for idx, link in n.links.iterrows():
            try:
                lat0, lon0 = _bus_coords(link.bus0)
                lat1, lon1 = _bus_coords(link.bus1)
            except (KeyError, AttributeError):
                continue
            _add_segment('dc_link', lat0, lon0, lat1, lon1)

    # ---- Build traces ----
    traces = []

    # 1) Non-investment network traces (single width per group)
    if voltage_aware:
        base_order = [
            ('line_high', NPAP_LINE_HIGH_VOLTAGE_COLOR, 'HV Lines (>300 kV)'),
            ('line_low',  NPAP_LINE_LOW_VOLTAGE_COLOR,  'LV Lines (\u2264300 kV)'),
            ('trafo',     NPAP_TRAFO_COLOR,             'Transformers'),
            ('dc_link',   NPAP_DC_LINK_COLOR,           'DC Links'),
        ]
    else:
        base_order = [
            ('line_existing', NPAP_UNIFORM_LINE_COLOR,  'Existing Network'),
            ('dc_link',       NPAP_DC_LINK_COLOR,       'DC Links'),
        ]

    for key, color, legend_name in base_order:
        if key not in groups:
            continue
        g = groups[key]
        traces.append(go.Scattermapbox(
            lon=g['lons'],
            lat=g['lats'],
            mode='lines',
            line=dict(width=2.5, color=color),
            name=f"{legend_name} ({g['count']})",
            hoverinfo='name',
            legendgroup=key,
        ))

    # 2) Investment lines – thicker lines keeping their original voltage color
    #    Bucket by (color_key, width_bucket) so each trace has uniform color+width.
    if inv_lines:
        max_exp = max(e for _, _, _, _, e, _ in inv_lines)

        # Map color keys to actual colors
        COLOR_KEY_MAP = {
            'line_high': NPAP_LINE_HIGH_VOLTAGE_COLOR,
            'line_low': NPAP_LINE_LOW_VOLTAGE_COLOR,
            'line_existing': NPAP_UNIFORM_LINE_COLOR,
        }

        WIDTH_BUCKETS = 8
        # keyed by (color_key, bucket_idx)
        bucket_data = {}

        for lat0, lon0, lat1, lon1, expansion, color_key in inv_lines:
            w = _investment_line_width(expansion, max_exp)
            bucket_idx = min(int((w - 3.5) / (12.0 - 3.5) * WIDTH_BUCKETS), WIDTH_BUCKETS - 1)
            bucket_idx = max(0, bucket_idx)
            bkey = (color_key, bucket_idx)
            if bkey not in bucket_data:
                bucket_data[bkey] = dict(lats=[], lons=[], count=0, width=0.0, color_key=color_key)
            b = bucket_data[bkey]
            b['lats'].extend([lat0, lat1, None])
            b['lons'].extend([lon0, lon1, None])
            b['count'] += 1
            b['width'] = max(b['width'], w)

        first_bucket = True
        for b in bucket_data.values():
            if b['count'] == 0:
                continue
            traces.append(go.Scattermapbox(
                lon=b['lons'],
                lat=b['lats'],
                mode='lines',
                line=dict(width=b['width'], color=COLOR_KEY_MAP.get(b['color_key'], NPAP_UNIFORM_LINE_COLOR)),
                name=f"Line Investment ({len(inv_lines)})" if first_bucket else '',
                hoverinfo='name',
                legendgroup='investment_line',
                showlegend=first_bucket,
            ))
            first_bucket = False

    # 3) Investment trafos – real bus0/bus1 coordinates, width ~ expansion
    if inv_trafos:
        max_exp_t = max(e for _, _, _, _, e in inv_trafos)

        TRAFO_WIDTH_BUCKETS = 8
        tbucket_data = [dict(lats=[], lons=[], count=0, width=0.0) for _ in range(TRAFO_WIDTH_BUCKETS)]

        for lat0, lon0, lat1, lon1, expansion in inv_trafos:
            w = _investment_line_width(expansion, max_exp_t)
            bucket_idx = min(int((w - 2.0) / (10.0 - 2.0) * TRAFO_WIDTH_BUCKETS), TRAFO_WIDTH_BUCKETS - 1)
            bucket_idx = max(0, bucket_idx)
            tb = tbucket_data[bucket_idx]
            tb['lats'].extend([lat0, lat1, None])
            tb['lons'].extend([lon0, lon1, None])
            tb['count'] += 1
            tb['width'] = max(tb['width'], w)

        first_tbucket = True
        for tb in tbucket_data:
            if tb['count'] == 0:
                continue
            traces.append(go.Scattermapbox(
                lon=tb['lons'],
                lat=tb['lats'],
                mode='lines',
                line=dict(width=tb['width'], color=NPAP_TRAFO_INVESTMENT_COLOR),
                name=f"Trafo Investment ({len(inv_trafos)})" if first_tbucket else '',
                hoverinfo='name',
                legendgroup='investment_trafo',
                showlegend=first_tbucket,
            ))
            first_tbucket = False

    # 4) Bus nodes – small dots at each bus location
    bus_lats = n.buses['y'].tolist()
    bus_lons = n.buses['x'].tolist()
    bus_texts = [str(idx) for idx in n.buses.index]
    traces.append(go.Scattermapbox(
        lon=bus_lons,
        lat=bus_lats,
        mode='markers',
        marker=dict(size=12, color=NPAP_NODE_COLOR, opacity=0.8),
        text=bus_texts,
        hoverinfo='text',
        name=f"Buses ({len(n.buses)})",
        legendgroup='buses',
    ))

    return traces


def plot_network_paper(n: pypsa.Network, output_file: str,
                       voltage_aware: bool = True,
                       regions: Optional[list] = None,
                       fmt: str = 'pdf',
                       show: bool = False,
                       show_title: bool = True,
                       show_legend: bool = True,
                       min_line_investment: float = 0.0,
                       min_trafo_investment: float = 0.0):
    """
    Generate paper-quality plots in NPAP style using Plotly + carto-positron.

    For voltage-aware networks:
      - Lines colored by voltage level (NPAP palette: green HV, brown LV)
      - Transformers in yellow, DC links in pink
      - Line investment in orange-red (width ~ expansion MVA)
      - Trafo investment as dark magenta line segments (width ~ expansion MVA)

    For voltage-unaware networks:
      - All existing lines in uniform dark gray
      - Same investment rendering as above

    Saves static images (pdf/png/svg) and the interactive HTML.

    Args:
        n: Solved PyPSA network.
        output_file: Base results directory.
        voltage_aware: If True, color lines by voltage level; if False, uniform color.
        regions: List of region keys to plot (default: ['europe', 'adria']).
        fmt: Output format ('pdf', 'png', 'svg').
        dpi: Resolution for raster formats.
        show: If True, also open the interactive plot in the browser.
        show_title: If True, display the network name as title.
        show_legend: If True, display the color legend.
        min_line_investment: Minimum expansion (MVA) for a line to appear as investment.
            Lines below this threshold are shown as regular network lines.
        min_trafo_investment: Minimum expansion (MVA) for a trafo to appear as investment.
            Trafos below this threshold are shown as regular transformers.
    """
    import plotly.graph_objects as go
    import plotly.io as pio

    if regions is None:
        regions = ['europe', 'adria']

    out_dir = os.path.join(output_file, n.name)
    os.makedirs(out_dir, exist_ok=True)

    # Build traces (shared across regions, we just change the map view)
    traces = _build_branch_traces(n, voltage_aware,
                                  min_line_investment=min_line_investment,
                                  min_trafo_investment=min_trafo_investment)

    suffix = 'va' if voltage_aware else 'non_va'

    for region in regions:
        view = REGION_VIEWS.get(region, REGION_VIEWS['europe'])

        # -- Shared layout options --
        base_layout = dict(
            paper_bgcolor=NPAP_BG_COLOR,
            hovermode='closest',
            showlegend=show_legend,
            mapbox=dict(
                style=NPAP_MAP_STYLE,
                bearing=0,
                center=dict(lat=view['center_lat'], lon=view['center_lon']),
                pitch=0,
                zoom=view['zoom'],
            ),
            margin=dict(r=0, t=0 if not show_title else 30, l=0, b=0),
        )

        if show_title:
            base_layout.update(
                title_text=n.name,
                title_font=dict(color='white', size=20, family='Arial, sans-serif'),
                title_y=0.994,
                title_x=0.5,
                title_xanchor='center',
            )

        if show_legend:
            base_layout['legend'] = dict(
                yanchor='top', y=0.99,
                xanchor='left', x=0.01,
                bgcolor='rgba(255,255,255,0.95)',
                bordercolor=NPAP_BG_COLOR,
                borderwidth=1,
                font=dict(size=11),
                itemsizing='constant',
                tracegroupgap=5,
            )

        # -- Interactive HTML: fullscreen (fills browser window) --
        fig_html = go.Figure(data=traces)
        fig_html.update_layout(**base_layout, autosize=True)

        html_path = os.path.join(out_dir, f'map_{suffix}_{region}.html')
        fig_html.write_html(
            html_path,
            config={'scrollZoom': True},
            full_html=True,
            default_width='100vw',
            default_height='100vh',
        )
        logging.info(f"Saved interactive plot: {html_path}")

        # -- Static image: large fixed size for paper-quality export --
        static_w = 3200 if region == 'europe' else 2400
        static_h = 2400
        fig_static = go.Figure(data=traces)
        fig_static.update_layout(**base_layout, width=static_w, height=static_h)

        img_path = os.path.join(out_dir, f'map_{suffix}_{region}.{fmt}')
        try:
            fig_static.write_image(img_path, scale=6 if fmt == 'png' else 2)
            logging.info(f"Saved static image: {img_path}")
        except Exception as e:
            logging.warning(
                f"Could not save static image ({e}). "
                f"Install kaleido: pip install -U kaleido"
            )

        if show:
            pio.renderers.default = 'browser'
            fig.show(config={'scrollZoom': True})


def plot_network(n: pypsa.Network, output_file: str):
    """
    Generates a static geographical plot of the PyPSA network and saves it as an SVG file.

    The plot visualizes buses as red points and lines as black lines on a
    PlateCarree projection. The output file path is constructed based on
    the provided `output_file` and the network's name.

    Args:
        n (pypsa.Network): The PyPSA network to plot.
        output_file (str): The base directory path where the plot HTML file
                           will be saved within a subdirectory named after the network.
    """
    try:
        logging.info(f"Generating static plot and saving to {output_file}...")

        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.join(output_file, n.name)), exist_ok=True)

        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())

        n.plot(ax=ax, bus_color='red', line_color='black', line_width=2)
        fig.savefig(os.path.join(output_file, n.name, 'map.svg'))


    except Exception as e:
        logging.error(f"{e}")


def plot_network_interactive(n: pypsa.Network, output_file: str, 
                             line_color_func: Callable = get_line_colors_by_voltage,
                             line_width_func: Callable = None,
                             transformer_color_func: Callable = None,
                             transformer_width_func: Callable = None):
    """
    Generates an interactive geographical plot of the PyPSA network using `n.explore()`
    and saves it to an HTML file.

    This function can visualize the network with different line colorings and widths by passing
    appropriate functions. By default, it colors lines by voltage level.

    Args:
        n (pypsa.Network): The PyPSA network to plot.
        output_file (str): The base directory path where the plot HTML file
                           will be saved within a subdirectory named after the network.
        line_color_func (Callable): A function that takes a PyPSA network and returns a
                                    pandas Series of line colors. Defaults to
                                    `get_line_colors_by_voltage`.
        line_width_func (Callable, optional): A function that takes a PyPSA network and returns a
                                              pandas Series of line widths.
        transformer_color_func (Callable, optional): A function that takes a PyPSA network and returns a
                                                     pandas Series of transformer colors.
        transformer_width_func (Callable, optional): A function that takes a PyPSA network and returns a
                                                     pandas Series of transformer widths.
    """
    try:
        logging.info(f"Generating interactive plot and saving to {output_file}...")

        # Ensure the directory exists
        os.makedirs(os.path.join(output_file, n.name), exist_ok=True)

        line_color = line_color_func(n)
        line_width = line_width_func(n) if line_width_func else 2
        
        transformer_color = transformer_color_func(n) if transformer_color_func else 'orange'
        transformer_width = transformer_width_func(n) if transformer_width_func else 3

        map = n.explore(line_color=line_color,
                        line_width=line_width,
                        transformer_color=transformer_color,
                        transformer_width=transformer_width,
                        tooltip=True,
                        jitter=0.05, )
        map.to_html(os.path.join(output_file, n.name, 'interactive_map.html'))
    except Exception as e:
        logging.error(f"{e}")


def plot_network_with_results_interactive(n: pypsa.Network, output_file: str):
    """
    Generates an interactive geographical plot of the PyPSA network, incorporating
    simulation results like line and link flows, and saves it to an HTML file.

    This function leverages `n.explore()` to visualize the network, with options
    to represent line and link flows. The plot is saved within a subdirectory
    named after the network inside the specified `output_file` path.

    Args:
        n (pypsa.Network): The PyPSA network with simulation results to plot.
        output_file (str): The base directory path where the plot HTML file
                           will be saved within a subdirectory named after the network.
    """
    try:
        logging.info(f"Generating interactive plot and saving to {output_file}...")

        line_flow = n.lines_t.p0.sum(axis=0)/len(n.lines_t.p0)
        link_flow = n.links_t.p0.sum(axis=0)/len(n.links_t.p0)

        map = n.explore(
            # bus_size=eb,
            bus_split_circle=True,
            # line_width=line_flow,
            # link_width=link_flow,
            line_flow=line_flow,
            link_flow=link_flow,
        )
        os.makedirs(os.path.join(output_file, n.name), exist_ok=True)
        map.to_html(os.path.join(output_file, n.name, 'interactive_map.html'))
    except Exception as e:
        logging.error(f"{e}")
