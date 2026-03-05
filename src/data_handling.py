"""
Module for loading and preparing the initial PyPSA network data.
"""
import logging
import os

import networkx as nx
import numpy as np
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
        logging.info(f"Overriding test case from config with provided case: {case}")
    else:
        case = config['test_case']

    path_to_network = os.path.join(config['pypsa_eur_test_case_path'], 'networks', case)

    logging.info(f"Attempting to load network from: {path_to_network}")

    n_full = pypsa.Network(path_to_network)

    if case is None:  # make sure that presolved networks are not named the same
        n_full.name = 'full_model'

    return n_full


def remove_non_ac_buses_and_links(n: pypsa.Network) -> pypsa.Network:
    """
    Identifies buses with carrier 'battery' or 'H2', removes them, and then removes
    all other components (generators, loads, storage units, stores, and links)
    attached to those buses.

    Args:
        n (pypsa.Network): The PyPSA network to clean.

    Returns:
        pypsa.Network: The network with non-AC infrastructure and attached components removed.
    """
    # Identify buses to remove
    buses_to_remove = n.buses.index[n.buses.carrier.isin(['battery', 'H2'])]

    if not buses_to_remove.empty:
        num_buses = len(buses_to_remove)

        # Remove attached components for each type
        for component in ["Generator", "Load", "StorageUnit", "Store", "Link"]:
            df = n.df(component)
            if df.empty:
                continue
            
            if component == "Link":
                # Links have bus0 and bus1
                mask = df.bus0.isin(buses_to_remove) | df.bus1.isin(buses_to_remove)
            else:
                # Generators, Loads, StorageUnits, and Stores have a 'bus' column
                mask = df.bus.isin(buses_to_remove)
            
            items_to_remove = df.index[mask]
            if not items_to_remove.empty:
                n.remove(component, items_to_remove)
                logging.info(f"Pre-processing: Removed {len(items_to_remove)} {component}s attached to non-AC buses.")

        # Finally remove the buses
        n.remove("Bus", buses_to_remove)
        logging.info(f"Pre-processing: Removed {num_buses} buses ('battery'/'H2').")
    
    return n


def preprocess_network(n: pypsa.Network, config: dict) -> pypsa.Network:
    """
    Preprocesses the PyPSA network based on the provided configuration.

    Args:
        n (pypsa.Network): The original PyPSA network to preprocess.

    Returns:
        pypsa.Network: The preprocessed PyPSA network.
    """

    # Remove non-AC infrastructure (battery and H2 buses/links)
    n = remove_non_ac_buses_and_links(n)

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
    # n = _add_estimated_transformer_data(n)

    # Define line capacities for lines with s_nom = 0
    n = _define_line_capacities(n)

    # Set standard voltage levels (220/380 kV)
    # n = _set_standard_voltages(n)

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


def _set_standard_voltages(n: pypsa.Network) -> pypsa.Network:
    """
    Sets the nominal voltage levels (v_nom) for buses and lines to standard
    values of 220 kV or 380 kV based on a 300 kV threshold.

    Args:
        n (pypsa.Network): The PyPSA network to update.

    Returns:
        pypsa.Network: The updated PyPSA network.
    """
    # Update buses
    n.buses.loc[n.buses.v_nom < 300, 'v_nom'] = 220
    n.buses.loc[n.buses.v_nom >= 300, 'v_nom'] = 380

    # Update lines
    n.lines.loc[n.lines.v_nom < 300, 'v_nom'] = 220
    n.lines.loc[n.lines.v_nom >= 300, 'v_nom'] = 380

    logging.info("Standardized voltage levels to 220 kV and 380 kV.")

    return n


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
        logging.warning(f"{file_path} not found. Skipping estimated transformer data.")
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


def _define_line_capacities(n: pypsa.Network) -> pypsa.Network:
    """
    Defines s_nom for lines where s_nom is 0, based on their type and num_parallel.
    Calculation: s_nom = sqrt(3) * v_nom * i_nom * num_parallel

    Args:
        n (pypsa.Network): The PyPSA network to update.

    Returns:
        pypsa.Network: The updated PyPSA network.
    """

    # Find lines with s_nom == 0 and a valid type
    mask = (n.lines.s_nom == 0) & (n.lines.type != "")

    if mask.any():
        # Map i_nom from line_types
        i_nom = n.lines.loc[mask, 'type'].map(n.line_types.i_nom)

        # Only update where i_nom was found
        update_mask = mask & i_nom.notna()

        if update_mask.any():
            # s_nom [MVA] = sqrt(3) * v_nom [kV] * i_nom [kA] * num_parallel
            n.lines.loc[update_mask, 's_nom'] = (
                np.sqrt(3) *
                n.lines.loc[update_mask, 'v_nom'] *
                i_nom.loc[update_mask] *
                n.lines.loc[update_mask, 'num_parallel']
            )

    return n


def set_congested_lines_and_transformers_extendable(n: pypsa.Network, threshold: float = 0.8) -> pypsa.Network:
    """
    Identifies congested lines and transformers in the network based on power flow
    results and sets the 's_nom_extendable' attribute to True for those components.

    A component is considered congested if its maximum absolute power flow across all
    snapshots is greater than or equal to the specified threshold of its nominal
    capacity (s_nom).

    Args:
        n (pypsa.Network): The PyPSA network with results.
        threshold (float): The loading threshold to consider a component congested.
                          Defaults to 0.95.

    Returns:
        pypsa.Network: The network with updated 's_nom_extendable' for lines and transformers.
    """
    # 1. Handle Lines
    if not n.lines_t.p0.empty:
        # Loading = max(|flow|) / (s_nom * s_max_pu)
        s_max_pu = n.lines.get('s_max_pu', 1.0)
        s_nom = n.lines.s_nom

        # Ensure we only check lines that have flow data
        lines_with_results = n.lines.index.intersection(n.lines_t.p0.columns)
        if not lines_with_results.empty:
            max_flow = n.lines_t.p0[lines_with_results].abs().max()
            capacity = (s_nom * s_max_pu).loc[lines_with_results]

            # Avoid division by zero
            loading = max_flow / capacity.replace(0, np.inf)

            congested_lines = loading[loading >= threshold].index

            logging.info(f"Identified {len(congested_lines)} congested lines (loading >= {threshold}).")

            n.lines['s_nom_extendable'] = False
            if not congested_lines.empty:
                n.lines.loc[congested_lines, 's_nom_extendable'] = True
    else:
        logging.warning("No power flow results found for lines. Cannot identify congested lines.")

    # 2. Handle Transformers
    if not n.transformers_t.p0.empty:
        s_max_pu_trafo = n.transformers.get('s_max_pu', 1.0)
        s_nom_trafo = n.transformers.s_nom

        trafos_with_results = n.transformers.index.intersection(n.transformers_t.p0.columns)
        if not trafos_with_results.empty:
            max_flow_trafo = n.transformers_t.p0[trafos_with_results].abs().max()
            capacity_trafo = (s_nom_trafo * s_max_pu_trafo).loc[trafos_with_results]

            loading_trafo = max_flow_trafo / capacity_trafo.replace(0, np.inf)

            congested_trafos = loading_trafo[loading_trafo >= threshold].index

            logging.info(f"Identified {len(congested_trafos)} congested transformers (loading >= {threshold}).")

            n.transformers['s_nom_extendable'] = False
            if not congested_trafos.empty:
                n.transformers.loc[congested_trafos, 's_nom_extendable'] = True
    else:
        logging.info("No power flow results found for transformers.")

    return n


def set_expanded_generation_as_default(n: pypsa.Network) -> pypsa.Network:
    """
    Sets p_nom to p_nom_opt for all generators to finalize the generation expansion results.

    Args:
        n (pypsa.Network): The PyPSA network with optimization results.

    Returns:
        pypsa.Network: The network with updated p_nom for generators.
    """
    if 'p_nom_opt' in n.generators.columns:
        n.generators['p_nom'] = n.generators['p_nom_opt']
        logging.info("Finalized generator expansion: Set p_nom to p_nom_opt.")
    else:
        logging.warning("p_nom_opt not found in generators. p_nom was not updated.")

    return n


def add_alternative_shortest_path_routes(n: pypsa.Network, config: dict) -> pypsa.Network:
    """
    Identifies alternative routes for extendable lines using a different voltage level.
    The logic finds the shortest path between the terminals of a congested line
    using only components (lines) of a different voltage level and transformers.
    """
    if 'voltage_comparison_map' not in config.get('optimization_options', {}):
        voltage_comparison_map = {220: 380, 380: 220}
    else:
        voltage_comparison_map = config['optimization_options']['voltage_comparison_map']

    extendable_lines = n.lines[n.lines.s_nom_extendable].index
    if extendable_lines.empty:
        logging.info("No extendable lines found. Skipping alternative path search.")
        return n

    logging.info('Searching for alternative routes for congested lines using different voltage levels...')

    congested_voltages = n.lines.loc[extendable_lines, 'v_nom'].unique()

    for v_orig in congested_voltages:
        # Build a graph excluding lines of v_orig
        G = nx.Graph()

        # Add lines that are NOT of v_orig
        for idx, line in n.lines.iterrows():
            if abs(line.v_nom - v_orig) > 10:
                if G.has_edge(line.bus0, line.bus1):
                    if line.length < G[line.bus0][line.bus1]['weight']:
                        G.add_edge(line.bus0, line.bus1, weight=line.length, type='line', index=idx)
                else:
                    G.add_edge(line.bus0, line.bus1, weight=line.length, type='line', index=idx)

        # Add all transformers
        for idx, trafo in n.transformers.iterrows():
            weight = 10.0  # Small penalty for trafo to represent voltage level change
            if G.has_edge(trafo.bus0, trafo.bus1):
                if weight < G[trafo.bus0][trafo.bus1]['weight']:
                    G.add_edge(trafo.bus0, trafo.bus1, weight=weight, type='transformer', index=idx)
            else:
                G.add_edge(trafo.bus0, trafo.bus1, weight=weight, type='transformer', index=idx)

        # For each extendable line of this voltage
        current_v_lines = n.lines.loc[extendable_lines]
        current_v_lines = current_v_lines[np.abs(current_v_lines.v_nom - v_orig) < 10]

        for l_idx in current_v_lines.index:
            line = n.lines.loc[l_idx]
            try:
                path_nodes = nx.shortest_path(G, source=line.bus0, target=line.bus1, weight='weight')
                for i in range(len(path_nodes) - 1):
                    u, v = path_nodes[i], path_nodes[i + 1]
                    edge_data = G[u][v]
                    if edge_data['type'] == 'line':
                        n.lines.at[edge_data['index'], 's_nom_extendable'] = True
                    elif edge_data['type'] == 'transformer':
                        n.transformers.at[edge_data['index'], 's_nom_extendable'] = True
                logging.info(f"Added alternative route for congested line {l_idx} ({v_orig} kV).")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                logging.info(f"No alternative path found for congested line {l_idx} ({v_orig} kV).")
                pass

    return n
