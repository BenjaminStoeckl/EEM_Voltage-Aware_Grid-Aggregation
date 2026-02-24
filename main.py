"""
Main script to run the grid aggregation testing framework.
"""

import logging
import os
import argparse

import yaml

from src import data_handling, temporal_clustering, model_runner, plotting
from src.aggregation import pypsa_native

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def main():
    """
    Orchestrates the entire workflow for comparing grid aggregation methods.
    """
    parser = argparse.ArgumentParser(description="Run the grid aggregation testing framework.")
    parser.add_argument(
        "config_file",
        nargs="?",  # Makes the argument optional
        default="testconfig_1d.yaml",
        help="Path to the configuration file (e.g., config_5d.yaml or testconfig_1d.yaml)",
    )
    args = parser.parse_args()

    # 0. Load configuration
    logging.info(f"Loading configuration from {args.config_file}")
    with open(args.config_file) as f:
        config = yaml.safe_load(f)

    # 1. Load a plottable PyPSA example network
    n_full = data_handling.load_network(config)

    # 2. Plot the initial grid setup for verification
    # 2.a Plot as picture
    # plotting.plot_network(n_full, config['results_path'])
    # # 2.b Plot as interactive map (optional, requires plotly)
    # plotting.plot_network_interactive(n_full, config['results_path'])

    # Aggregate stub lines to simplify the network for testing
    n_agg_stub = pypsa_native.aggregate_stubs(n_full)
    n_agg_stub.name = 'Eur_full_model_agg_stub'

    # plotting.plot_network(n_agg_stub, config['results_path'])
    # plotting.plot_network_interactive(n_agg_stub, config['results_path'])

    # 3. Cluster the test case temporally
    n_temporal_clustered = temporal_clustering.aggregate_temporally_by_clustering(n_agg_stub, config['temporal_clustering'])
    n_temporal_clustered.name = 'Eur_stub_agg_model_temporal_clustered'

    # 3. Configure and run the full, but temporally clustered, model for expansion planning
    logging.info("Running expansion planning for the full (unaggregated) model.")
    n_temporal_clustered = model_runner.run_expansion_planning(
        n_temporal_clustered, "full_model", config
    )
    n_temporal_clustered.export_to_netcdf(os.path.join(config['results_path'], 'networks', n_temporal_clustered.name + '.nc'))
    plotting.plot_network_with_results_interactive(n_temporal_clustered, config['results_path'])

    #
    # # 4. Aggregate the grid with built-in PyPSA methods
    # logging.info("Aggregating the grid using native PyPSA methods (geographical).")
    # n_aggregated_pypsa = pypsa_native.aggregate(
    #     n_clustered.copy(), config['aggregation_options']
    # )
    #
    # # 5. Run the PyPSA-aggregated model
    # logging.info("Running expansion planning for the PyPSA-aggregated model.")
    # pypsa_aggregated_results_path = model_runner.run_expansion_planning(
    #     n_aggregated_pypsa, "pypsa_aggregated", config
    # )
    #
    # # 6. Prepare for voltage-aware aggregation (placeholder step)
    # logging.info("Preparing for voltage-aware aggregation (placeholder).")
    # try:
    #     voltage_aware.aggregate(n_clustered.copy(), config['voltage_aware_options'])
    # except NotImplementedError as e:
    #     logging.warning(f"Skipping voltage-aware aggregation: {e}")
    #     voltage_aggregated_results_path = None

    # # 7. Compare the results
    # logging.info("Comparing results between the full model and aggregated versions.")
    # postprocessing.compare_results(
    #     full_model_path=full_model_results_path,
    #     aggregated_model_paths={
    #         "pypsa_native": pypsa_aggregated_results_path,
    #         "voltage_aware": voltage_aggregated_results_path,
    #     },
    #     config=config
    # )


    logging.info("Workflow completed.")


if __name__ == "__main__":
    main()
