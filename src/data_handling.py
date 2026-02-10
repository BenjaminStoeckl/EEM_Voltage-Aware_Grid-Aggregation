"""
Module for loading and preparing the initial PyPSA network data.
"""
import pypsa
import os

def load_network(path_to_network: str) -> pypsa.Network:
    """
    Loads a PyPSA network from a given file path.

    Args:
        path_to_network (str): The file path to the network data (e.g., .nc file).

    Returns:
        pypsa.Network: The loaded PyPSA network object.
    """

    print(f"Attempting to load network from: {path_to_network}")

    n_full = pypsa.Network(path_to_network)

    n_full.add("Generator", n_full.buses.index + " slack",
          bus=n_full.buses.index,
          p_nom=10000,
          marginal_cost=10000,
          carrier="slack")

    n_full.sanitize()


    return pypsa.Network(path_to_network)
