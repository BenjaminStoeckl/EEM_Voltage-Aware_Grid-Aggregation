"""
Main script to run the grid aggregation testing framework.
"""

import argparse
import logging
import os

import yaml

from src import data_handling, temporal_clustering, model_runner, plotting, model_analyzer
from src.aggregation import pypsa_native, npap_clustering

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def main():
    """
    Orchestrates the entire workflow for comparing grid aggregation methods.
    """
    # -------------------------------------------------------------------------
    # 1. Argument Parsing & Initialization
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(description="Run the grid aggregation testing framework.")
    parser.add_argument(
        "config_file",
        nargs="?",  # Makes the argument optional
        default="testconfig_1d.yaml",
        help="Path to the configuration file (e.g., config_5d.yaml or testconfig_1d.yaml)",
    )
    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # 2. Configuration Loading
    # -------------------------------------------------------------------------
    logging.info(f"Loading configuration from {args.config_file}")
    with open(args.config_file) as f:
        config = yaml.safe_load(f)

    # -------------------------------------------------------------------------
    # 3. Network Loading & Pre-processing
    # -------------------------------------------------------------------------
    pypsa_model = data_handling.load_network(config)

    if config['preprocess_test_case']:
        logging.info(f"Pre-processing test case")
        pypsa_model = data_handling.preprocess_network(pypsa_model, config)

    # -------------------------------------------------------------------------
    # 4. Initial Network Simplification (Stubs & Temporal)
    # -------------------------------------------------------------------------
    if config['aggregate_stub_lines']:
        # Aggregate stub lines to simplify the network for testing
        pypsa_model = pypsa_native.aggregate_stubs(pypsa_model)
        pypsa_model.name = 'model_agg_stubs'

    if config['temporal_aggregation']:
        # Cluster the test case temporally
        pypsa_model = temporal_clustering.aggregate_temporally_by_clustering(pypsa_model, config['temporal_clustering'])
        pypsa_model.name = 'model_clustered_temporal'

    # Save the base model state
    pypsa_model.export_to_netcdf(os.path.join(config['results_path'], 'networks', pypsa_model.name + '.nc'))
    plotting.plot_network_interactive(pypsa_model, config['results_path'])

    # -------------------------------------------------------------------------
    # 5. Full Model Baseline Execution
    # -------------------------------------------------------------------------
    if config['run_full_model']:
        logging.info("Running expansion planning for the full (unaggregated) model.")
        full_pypsa_model = model_runner.run_expansion_planning(pypsa_model, "full_model", config)

        model_analyzer.analyze_network_results([full_pypsa_model])

        full_pypsa_model.export_to_netcdf(os.path.join(config['results_path'], 'networks', full_pypsa_model.name + '.nc'))
        pypsa_model.model.solver_model = None  # Clear the solver model to enable copying the network

        plotting.plot_network_with_results_interactive(pypsa_model, config['results_path'])

    # -------------------------------------------------------------------------
    # 6. Grid Aggregation: NPAP - VA Aggregation
    # -------------------------------------------------------------------------
    if config['aggregate_geo_va']:
        logging.info("Aggregating the grid using geographical, voltage-aware clustering.")
        n_agg_geo_va = npap_clustering.aggregate(pypsa_model.copy(), config['geo_va_aggregation'])

        n_agg_geo_va = model_runner.run_expansion_planning(n_agg_geo_va, 'model_geo_va_agg', config)

        n_agg_geo_va.export_to_netcdf(os.path.join(config['results_path'], 'networks', n_agg_geo_va.name + '.nc'))
        plotting.plot_network_interactive(n_agg_geo_va, config['results_path'])

    # -------------------------------------------------------------------------
    # 7. Grid Aggregation: NPAP - non VA Aggregation
    # -------------------------------------------------------------------------
    if config['aggregate_geo_non_va']:
        logging.info("Aggregating the grid using geographical, non-voltage-aware clustering.")
        n_agg_geo_non_va = npap_clustering.aggregate(pypsa_model.copy(), config['geo_non_va_aggregation'])

        n_agg_geo_non_va = model_runner.run_expansion_planning(n_agg_geo_non_va, 'model_geo_non_va_agg', config)

        n_agg_geo_non_va.export_to_netcdf(os.path.join(config['results_path'], 'networks', n_agg_geo_non_va.name + '.nc'))
        plotting.plot_network_interactive(n_agg_geo_non_va, config['results_path'])

    # -------------------------------------------------------------------------
    # 8. Results Analysis & Comparison
    # -------------------------------------------------------------------------
    logging.info("Comparing results between the full model and aggregated versions.")
    model_analyzer.analyze_active_slack_nodes(pypsa_model)
    if config['aggregate_geo_va'] and config['aggregate_geo_non_va']:
        model_analyzer.analyze_active_slack_nodes(n_agg_geo_va)
        model_analyzer.analyze_active_slack_nodes(n_agg_geo_non_va)
        model_analyzer.analyze_network_results([pypsa_model, n_agg_geo_va, n_agg_geo_non_va])

    logging.info("Workflow completed.")


if __name__ == "__main__":
    main()
