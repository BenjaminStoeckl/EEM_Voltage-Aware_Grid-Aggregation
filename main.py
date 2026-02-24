"""
Main script to run the grid aggregation testing framework.
"""

import logging
import os
import argparse

import yaml

from src import data_handling, temporal_clustering, model_runner, plotting, model_analyzer
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
    pypsa_model = data_handling.load_network(config)

    if config['preprocess_test_case']:
        logging.info(f"Pre-processing test case")
        n = data_handling.preprocess_network(pypsa_model)

    # 2. Plot the initial grid setup for verification
    # 2.a Plot as picture
    # plotting.plot_network(pypsa_model, config['results_path'])
    # # 2.b Plot as interactive map (optional, requires plotly)
    # plotting.plot_network_interactive(pypsa_model, config['results_path'])

    if config['aggregate_stub_lines']:
        # Aggregate stub lines to simplify the network for testing
        pypsa_model = pypsa_native.aggregate_stubs(pypsa_model)
        pypsa_model.name = 'model_agg_stubs'

    # plotting.plot_network(n_agg_stub, config['results_path'])
    # plotting.plot_network_interactive(n_agg_stub, config['results_path'])

    if config['temporal_aggregation']:
        # 3. Cluster the test case temporally
        pypsa_model = temporal_clustering.aggregate_temporally_by_clustering(pypsa_model, config['temporal_clustering'])
        pypsa_model.name = 'model_clustered_temporal'

    if config['run_full_model']:
        # 3. Configure and run the full, but temporally clustered, model for expansion planning
        logging.info("Running expansion planning for the full (unaggregated) model.")
        pypsa_model = model_runner.run_expansion_planning(
            pypsa_model, "full_model", config
        )

    model_analyzer.analyze_network_results([pypsa_model])

    pypsa_model.export_to_netcdf(os.path.join(config['results_path'], 'networks', pypsa_model.name + '.nc'))
    plotting.plot_network_with_results_interactive(pypsa_model, config['results_path'])

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
