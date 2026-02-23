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

    print(f"Attempting to load network from: {path_to_network}")

    n_full = pypsa.Network(path_to_network)
    n_full.name = 'Eur_full_model'

    # Add a slack generator to each bus to ensure feasibility
    n_full.add("Generator", n_full.buses.index + " slack",
               bus=n_full.buses.index,
               p_nom=10000,
               marginal_cost=10000,
               carrier="slack")

    # Sanitize the network (add slack bus, define carriers, etc.)
    n_full.sanitize()

    # Set num_parallel of lines to a minimum of 1, if the line is active, to avoid infinite impedance
    n_full.lines.loc[(n_full.lines.active & n_full.lines.num_parallel == 0), 'num_parallel'] = 1

    return n_full
