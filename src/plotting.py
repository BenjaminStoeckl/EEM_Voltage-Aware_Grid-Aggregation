"""
Module for generating various plots and visualizations of PyPSA networks.

This module provides functions for creating both static and interactive
representations of electrical grids, including geographical plots,
and visualizations incorporating simulation results.
"""

import logging
import os

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
    """
    Generates an interactive plot of the network using geopandas and plotly,
    and saves it to an HTML file.

    Requires the 'geopandas' and 'plotly' libraries.

    Args:
        n (pypsa.Network): The PyPSA network to plot.
        output_file (str): Path to save the output plot HTML file.
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


def plot_network_interactive(n: pypsa.Network, output_file: str):
    """
    Generates an interactive geographical plot of the PyPSA network using `n.explore()`
    and saves it to an HTML file.

    This function visualizes the network with lines colored by voltage level
    (using `get_line_colors_by_voltage`), includes transformer width, and tooltips
    for interactive inspection. The plot is saved within a subdirectory named
    after the network inside the specified `output_file` path.

    Args:
        n (pypsa.Network): The PyPSA network to plot.
        output_file (str): The base directory path where the plot HTML file
                           will be saved within a subdirectory named after the network.
    """
    """
    Generates an interactive plot of the network using geopandas and plotly,
    and saves it to an HTML file.

    Requires the 'geopandas' and 'plotly' libraries.

    Args:
        n (pypsa.Network): The PyPSA network to plot.
        output_file (str): Path to save the output plot HTML file.
    """
    try:
        logging.info(f"Generating interactive plot and saving to {output_file}...")

        # Ensure the directory exists
        os.makedirs(os.path.join(output_file, n.name), exist_ok=True)

        map = n.explore(line_color=get_line_colors_by_voltage(n),
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

        line_flow = n.lines_t.p0.sum(axis=0)
        link_flow = n.links_t.p0.sum(axis=0)

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
