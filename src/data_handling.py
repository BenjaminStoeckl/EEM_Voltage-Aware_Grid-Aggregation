"""
Module for loading and preparing the initial PyPSA network data.
"""
import pypsa

def load_network(path_to_network: str) -> pypsa.Network:
    """
    Loads a PyPSA network from a given file path.

    Args:
        path_to_network (str): The file path to the network data (e.g., .nc file).

    Returns:
        pypsa.Network: The loaded PyPSA network object.
    """
    # TODO: Add error handling for file not found
    print(f"Attempting to load network from: {path_to_network}")
    return pypsa.Network(path_to_network)
