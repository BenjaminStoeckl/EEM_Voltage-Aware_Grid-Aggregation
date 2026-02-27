"""
Module for loading and preparing the initial PyPSA network data.
"""
import os

import pandas as pd
import pypsa


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


def preprocess_network(n: pypsa.Network, config: dict) -> pypsa.Network:
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
          p_nom=10000,  # Set a high nominal power to ensure it can meet any demand
          marginal_cost=n.generators['marginal_cost'].max() * 2,  # Set a high marginal cost to discourage use
          carrier="slack")

    # Sanitize the network (add slack bus, define carriers, etc.)
    n.sanitize()

    # Set num_parallel of lines to a minimum of 1, if the line is active, to avoid infinite impedance
    n.lines.loc[(n.lines.active & n.lines.num_parallel == 0), 'num_parallel'] = 1

    # Add estimated transformer data
    n = _add_estimated_transformer_data(n)

    n = _add_network_expansion_costs(n, config['network_expansion_costs'])

    n.lines['s_nom_min'] = n.lines['s_nom']  # Set minimum capacity to current capacity to prevent reduction
    n.transformers['s_nom_min'] = n.transformers['s_nom']  # Set minimum capacity to current capacity to prevent reduction

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


def _add_network_expansion_costs(n: pypsa.Network, expansion_cost: dict) -> pypsa.Network:
    """
    Adds expansion cost attributes to the network's lines and generators based on the provided configuration.

    This function checks the configuration for line and generator expansion costs and updates the network's
    components accordingly. It ensures that the necessary columns for expansion costs are present in the
    network's lines and generators DataFrames, and fills them with the specified values from the configuration.

    Args:
        n (pypsa.Network): The PyPSA network to which expansion costs will be added.
            expansion_cost (dict): A dictionary containing expansion cost values for lines and generators, with keys:
                - 'line_expansion_cost_220': The annualized cost per unit of line capacity expansion.
                - 'line_expansion_cost_380': The annualized cost per unit of line capacity expansion.
                - 'trafo_expansion_cost_380-220': The annualized cost per unit of trafo capacity expansion.


    Returns:
        pypsa.Network: The updated PyPSA network with expansion cost attributes added.
    """
    # Add line expansion costs if specified in the config
    if 'line_expansion_cost_220' in expansion_cost:
        if expansion_cost['line_expansion_cost_220'] is not None:
            mask = n.lines['v_nom'] < 300
            if mask.any():
                n.lines.loc[mask, 'capital_cost'] = expansion_cost['line_expansion_cost_220'] * n.lines.loc[mask, 'length']

    # Add line expansion costs for 380kV lines if specified in the config
    if 'line_expansion_cost_380' in expansion_cost:
        if expansion_cost['line_expansion_cost_380'] is not None:
            mask = n.lines['v_nom'] >= 300
            if mask.any():
                n.lines.loc[mask, 'capital_cost'] = expansion_cost['line_expansion_cost_380'] * n.lines.loc[mask, 'length']

    # Add transformer expansion costs if specified in the config
    if 'trafo_expansion_cost_380-220' in expansion_cost:
        if expansion_cost['trafo_expansion_cost_380-220'] is not None:
            n.transformers['capital_cost'] = expansion_cost['trafo_expansion_cost_380-220']

    return n


def _add_estimated_transformer_data(n: pypsa.Network) -> pypsa.Network:
    """
    Adds estimated transformer data from a CSV file to the network.
    The data is matched based on 'bus0' and 'bus1' columns.
    Assigns 's_nom_estimated' to 's_nom' and 'reactance_x_estimated' to 'x' (after conversion to pu).
    Sets 'num_parallel' based on 'n_parallel', with a minimum of 1.

    Args:
        n (pypsa.Network): The PyPSA network to which estimated transformer data will be added.

    Returns:
        pypsa.Network: The updated PyPSA network.
    """

    file_path = os.path.join("data", "transformers_estimated.csv")
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found. Skipping estimated transformer data.")
        return n

    df_est = pd.read_csv(file_path, sep=',', decimal='.')

    # Ensure bus labels are strings to match PyPSA
    df_est['bus0'] = df_est['bus0'].astype(str)
    df_est['bus1'] = df_est['bus1'].astype(str)

    # Set multi-index for matching
    df_est = df_est.set_index(['bus0', 'bus1'])

    # Iterate and update transformers in n
    for idx, trafo in n.transformers.iterrows():
        b0, b1 = trafo.bus0, trafo.bus1

        # Try direct match
        if (b0, b1) in df_est.index:
            row = df_est.loc[(b0, b1)]
        # Try swapped match
        elif (b1, b0) in df_est.index:
            row = df_est.loc[(b1, b0)]
        else:
            continue

        # If multiple matches, take the first one
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]

        s_nom = row['s_nom_estimated']
        x_ohm = row['reactance_x_estimated']

        # Skip if estimated values are zero to avoid division by zero or invalid parameters
        if s_nom <= 0 or x_ohm <= 0:
            continue

        v_nom = max(row['voltage_bus0'], row['voltage_bus1'])  # Assumption: reactance (ohm) belongs to high voltage side (industry standard)

        # Convert to pu: x_pu = x_ohm * s_nom / v_nom^2
        x_pu = x_ohm * s_nom / (v_nom ** 2)

        n.transformers.at[idx, 's_nom'] = s_nom
        n.transformers.at[idx, 'x'] = x_pu
        n.transformers.at[idx, 'num_parallel'] = max(1, row['n_parallel'])

        # Clear type to ensure x is used instead of standard type parameters
        n.transformers.at[idx, 'type'] = ""

    return n
