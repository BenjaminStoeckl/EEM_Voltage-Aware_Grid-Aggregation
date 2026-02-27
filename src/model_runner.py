"""
Module for configuring and running the PyPSA optimization models.
"""
import os
from typing import Dict

import pypsa


def run_expansion_planning(n: pypsa.Network, model_name: str, config: Dict) -> pypsa.Network:
    """
    Configures and solves the network expansion planning problem.

    Args:
        n (pypsa.Network): The PyPSA network to be solved.
        model_name (str): A descriptive name for the model run (e.g., "full_model").
        config (Dict): The main configuration dictionary.

    Returns:
        str: The path to the solved network file.
    """
    results_dir = os.path.join(config['results_path'], model_name)
    os.makedirs(results_dir, exist_ok=True)

    # Configure the network for expansion planning
    # n.lines["s_nom_extendable"] = config['optimization_options']['include_line_expansion']

    if config['optimization_options']['include_line_expansion']:
        n.lines.loc[n.lines['under_construction'] == 1, 's_nom_extendable'] = True
        n.transformers['s_nom_extendable'] = True
    else:
        n.lines['s_nom_extendable'] = False
        n.transformers['s_nom_extendable'] = False

    # n.generators["p_nom_extendable"] = True

    print(f"Running optimization for '{model_name}'...")

    # A simple solve, replace with a proper optimization call
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
