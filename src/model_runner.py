"""
Module for configuring and running the PyPSA optimization models.
"""
import os
from typing import Dict

import numpy as np
import pandas as pd
import pypsa


def set_congested_lines_extendable(n: pypsa.Network) -> pypsa.Network:
    """
    Identifies congested lines and sets them as extendable.

    A line is considered congested if its power flow at any timestep
    is at or near its maximum capacity (>= 95% of s_max).

    Args:
        n (pypsa.Network): The PyPSA network, expected to contain power flow results.

    Returns:
        pypsa.Network: The updated PyPSA network with 's_nom_extendable' set for congested lines.
    """
    if n.lines_t.p0.empty:
        print("Warning: No time-dependent line data (n.lines_t.p0) found. Cannot determine congestion.")
        n.lines['s_nom_extendable'] = False  # Ensure it's set to False
        return n

    lines_with_flow_data = n.lines.index.intersection(n.lines_t.p0.columns)
    if lines_with_flow_data.empty:
        print("Warning: No power flow data found for any line in n.lines_t.p0. No lines will be set as extendable.")
        n.lines['s_nom_extendable'] = False  # Ensure it's set to False
        return n

    relevant_lines = n.lines.loc[lines_with_flow_data]
    relevant_p0 = n.lines_t.p0[lines_with_flow_data]

    s_max_abs = relevant_lines['s_nom'] * relevant_lines.get('s_max_pu', 1.0)

    max_abs_flow_per_line = relevant_p0.abs().max(axis=0)

    congested_lines_mask = (max_abs_flow_per_line >= 0.95 * s_max_abs)

    # Initialize all to not extendable
    n.lines['s_nom_extendable'] = False

    # Set extendable for congested lines
    congested_lines_index = congested_lines_mask[congested_lines_mask].index
    if not congested_lines_index.empty:
        n.lines.loc[congested_lines_index, 's_nom_extendable'] = True

    return n


def run_model_optimization(n: pypsa.Network, model_name: str, config: Dict, activate_line_expansion: bool = True) -> pypsa.Network:
    """
    Configures and solves the network expansion planning problem.

    Args:
        n (pypsa.Network): The PyPSA network to be solved.
        model_name (str): A descriptive name for the model run (e.g., "full_model").
        config (Dict): The main configuration dictionary.

    Returns:
        str: The path to the solved network file.
        :param activate_line_expansion: Whether to activate line expansion based on the configuration. This allows for flexibility in testing different scenarios without modifying the main configuration file.
    """
    results_dir = os.path.join(config['results_path'], model_name)
    os.makedirs(results_dir, exist_ok=True)

    n.lines['under_construction'] = False  # set all lines to not under construction by default

    if config['optimization_options']['include_line_expansion'] and activate_line_expansion:
        match config['optimization_options']['define_expandable_lines']:
            case 'all':
                n.lines['s_nom_extendable'] = True
                n.transformers['s_nom_extendable'] = True
            case 'all_congested_lines':
                n = set_congested_lines_extendable(n)
            case 'predefined':
                # don't change the existing 's_nom_extendable' values in the network, just ensure that transformers are consistent
                # n.transformers['s_nom_extendable'] = True
                pass
    else:
        n.lines['s_nom_extendable'] = False
        n.transformers['s_nom_extendable'] = False

    print(f"Running optimization for '{model_name}'...")

    try:
        path_temp_files = os.path.join(config['path_for_temporary_files'], 'pypsa_model.lp')
        n.optimize(solver_name="gurobi",
                   problem_fn=path_temp_files,
                   solver_options=config["solver_options"],
                   compute_infeasibilities=True,
                   include_objective_constant=True)

        print(f"Optimization for '{model_name}' complete (simulation).")
        n.name = f'{model_name}_solved'
    except Exception as e:
        print(f"Could not run optimization for '{model_name}', Error: {e}")

    # Save the results
    results_path = os.path.join(results_dir, "results.nc")
    # n.export_to_netcdf(results_path)
    # print(f"Results for '{model_name}' saved to '{results_path}' (simulation).")

    return n
