"""
Module for generating various plots and visualizations of PyPSA networks.

This module provides functions for creating both static and interactive
representations of electrical grids, including geographical plots,
and visualizations incorporating simulation results.
"""

import logging
import os
from typing import Callable

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


def plot_network_interactive(n: pypsa.Network, output_file: str, line_color_func: Callable = get_line_colors_by_voltage):
    """
    Generates an interactive geographical plot of the PyPSA network using `n.explore()`
    and saves it to an HTML file.

    This function can visualize the network with different line colorings by passing
    a coloring function to `line_color_func`. By default, it colors lines by voltage level.

    Args:
        n (pypsa.Network): The PyPSA network to plot.
        output_file (str): The base directory path where the plot HTML file
                           will be saved within a subdirectory named after the network.
        line_color_func (Callable): A function that takes a PyPSA network and returns a
                                    pandas Series of line colors. Defaults to
                                    `get_line_colors_by_voltage`.
    """
    try:
        logging.info(f"Generating interactive plot and saving to {output_file}...")

        # Ensure the directory exists
        os.makedirs(os.path.join(output_file, n.name), exist_ok=True)

        map = n.explore(line_color=line_color_func(n),
                        transformer_width=3,
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
