
import pypsa
import os
import logging
import matplotlib.pyplot as plt
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
from shapely.geometry import LineString

import cartopy.crs as ccrs

def plot_network(n: pypsa.Network, output_file: str):
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
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())

        n.plot(ax=ax, bus_color='red', line_color='black', line_width=2)
        fig.savefig('map.png')

        
    except Exception as e:
        logging.error(f"{e}")



