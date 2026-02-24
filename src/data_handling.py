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
    n_full.name = 'full_model'

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


def export_network_and_results(n: pypsa.Network, config: dict, file_name: str = "network") -> None:
    """
    Exports a PyPSA network, including any attached optimization results, to a NetCDF file.

    The output directory is determined from the 'results_path' key in the provided configuration dictionary.
    The function creates the specified output folder if it does not already exist.
    The network is saved in NetCDF format, which is suitable for storing PyPSA Network objects
    along with their components and attributes, including optimization results.

    Args:
        n (pypsa.Network): The PyPSA network object to export.
        config (dict): The dictionary containing configuration parameters, including 'results_path'.
        file_name (str, optional): The base name for the exported NetCDF file.
                                   Defaults to "network".
    """
    output_folder = os.path.normpath(config['results_path'])

    if not os.path.exists(output_folder):
        os.makedirs(output_folder, exist_ok=True)

    file_path = os.path.join(output_folder, f"{file_name}.nc")
    n.export_to_netcdf(file_path)