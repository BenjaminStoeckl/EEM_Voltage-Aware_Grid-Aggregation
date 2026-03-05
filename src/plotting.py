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
from pypsa.clustering.npap import plot_npap


def plot_npap_clustering(n: pypsa.Network, config: dict, label: str, busmap: pd.Series = None):
    """
    Plots the network using NPAP's interactive map plotting.
    Attempts to load the busmap from the results folder if not provided.
    """
    try:
        if busmap is None:
            results_dir = os.path.join(config['results_path'], label)
            busmap_path = os.path.join(results_dir, "busmap.csv")
            if os.path.exists(busmap_path):
                # Load busmap as Series. index_col=0 is the original bus name, column 0 is the cluster
                busmap = pd.read_csv(busmap_path, index_col=0).iloc[:, 0]
                logging.info(f"Loaded busmap from {busmap_path} for NPAP plotting.")
            else:
                logging.warning(f"No busmap found at {busmap_path}. Plotting without clusters.")

        # style="clustered" if busmap is present, else "voltage_aware"
        style = "clustered" if busmap is not None else "voltage_aware"

        # Ensure the results directory exists
        results_dir = os.path.join(config['results_path'], label)
        os.makedirs(results_dir, exist_ok=True)

        fig = plot_npap(n, busmap=busmap, style=style, show=False, title=f"NPAP Clustering: {label}",
                        include_links=True, include_transformers=True)

        # Save as HTML
        plot_path = os.path.join(results_dir, "npap_plot.html")
        fig.write_html(plot_path)
        logging.info(f"NPAP plot saved to {plot_path}")

    except Exception as e:
        logging.error(f"Error generating NPAP plot for {label}: {e}")


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


def get_line_widths_by_expansion(n: pypsa.Network, scale: float = 0.005, min_width: float = 2.0) -> pd.Series:
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

        line_flow = n.lines_t.p0.sum(axis=0) / len(n.lines_t.p0)
        link_flow = n.links_t.p0.sum(axis=0) / len(n.links_t.p0)

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
