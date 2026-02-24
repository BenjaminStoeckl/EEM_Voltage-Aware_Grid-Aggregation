"""
Module for loading and preparing the initial PyPSA network data.
"""
import pypsa
import os


def load_network(config: dict, case: str = None) -> pypsa.Network:
    """
    Loads a PyPSA network from a given file path.

    Args:
        config (dict): The dictionary containing configuration parameters, including:
            - 'pypsa_eur_test_case_path': The base path to the PyPSA test cases.
            - 'test_case': The specific test case file name to load.
        case (str, optional): An optional specific test case file name to load, which overrides the one specified in the config.

    Returns:
        pypsa.Network: The loaded PyPSA network object.
    """

    if case is not None:
        print(f"Overriding test case from config with provided case: {case}")
    else:
        case = config['test_case']

    path_to_network = os.path.join(config['pypsa_eur_test_case_path'], 'networks', case)

    print(f"Attempting to load network from: {path_to_network}")

    n_full = pypsa.Network(path_to_network)
    n_full.name = 'Eur_full_model'

    return n_full



def preprocess_network(n: pypsa.Network) -> pypsa.Network:
    """
    Preprocesses the PyPSA network based on the provided configuration.

    Args:
        n (pypsa.Network): The original PyPSA network to preprocess.

    Returns:
        pypsa.Network: The preprocessed PyPSA network.
    """


    # Add a slack generator to each bus to ensure feasibility
    n.add("Generator", n.buses.index + " slack",
               bus=n.buses.index,
               p_nom=10000,
               marginal_cost=10000,
               carrier="slack")

    # Sanitize the network (add slack bus, define carriers, etc.)
    n.sanitize()

    # Set num_parallel of lines to a minimum of 1, if the line is active, to avoid infinite impedance
    n.lines.loc[(n.lines.active & n.lines.num_parallel == 0), 'num_parallel'] = 1

    return n
