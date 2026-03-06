"""
Main script to run the grid aggregation testing framework.
"""

import argparse
import logging
import os
from datetime import datetime

import pypsa
import yaml

from src import data_handling, temporal_clustering, model_runner, plotting, model_analyzer
from src.aggregation import pypsa_native, npap_clustering


def main():
    """
    Orchestrates the entire workflow for comparing grid aggregation methods.
    """
    # Set up basic logging to console
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    # Add File Logging
    # -------------------------------------------------------------------------
    # Determine the number of nodes (clusters) for the filename
    num_nodes = "unknown"
    for key in ['geo_va_aggregation', 'geo_non_va_aggregation', 'elec_va_aggregation', 'elec_non_va_aggregation']:
        if isinstance(config.get(key), dict) and 'num_of_clusters' in config[key]:
            num_nodes = str(config[key]['num_of_clusters'])
            break

    # Setup logs directory in the results path
    logs_dir = os.path.join(config['results_path'], 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    log_filename = os.path.join(logs_dir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{num_nodes}nodes.txt")
    file_handler = logging.FileHandler(log_filename)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(file_handler)
    logging.info(f"Log output also saved to: {log_filename}")

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

    if config['preprocess_test_case'] or config['aggregate_stub_lines'] or config['temporal_aggregation']:
        # Save the base model state
        pypsa_model.export_to_netcdf(os.path.join(config['results_path'], 'networks', pypsa_model.name + '.nc'))
        plotting.plot_network_interactive(pypsa_model, config['results_path'], line_color_func=plotting.get_line_colors_by_voltage)
        plotting.plot_npap_clustering(pypsa_model, config, 'full_model_base')

    # -------------------------------------------------------------------------
    # 5. Full Model Baseline Execution
    # -------------------------------------------------------------------------
    if config['run_full_model_base']:
        logging.info("Running generation expansion planning for the full (unaggregated) model.")
        pypsa_model = model_runner.run_model_optimization(pypsa_model, "full_model_base", config, activate_line_expansion=False)

        model_analyzer.analyze_network_results([pypsa_model])

        # Identify congested lines and set them as extendable for the following aggregation steps
        pypsa_model = data_handling.set_congested_lines_and_transformers_extendable(pypsa_model, threshold=0.8)

        if config['add_alternative_shortest_path_routes']:
            pypsa_model = data_handling.add_alternative_shortest_path_routes(pypsa_model, config)
        pypsa_model = data_handling.set_expanded_generation_as_default(pypsa_model)

        if pypsa_model.model.solver_model is not None:
            pypsa_model.model.solver_model = None  # Clear the solver model to enable copying the network
        pypsa_model.generators['p_nom_extendable'] = False  # set all generators to not extendable by default

        pypsa_model.export_to_netcdf(os.path.join(config['results_path'], 'networks', pypsa_model.name + '.nc'))
        plotting.plot_network_interactive(pypsa_model, config['results_path'], line_color_func=plotting.get_line_colors_by_expansion)

    # -------------------------------------------------------------------------
    # 5. Full Model Grid Expansion Execution
    # -------------------------------------------------------------------------
    if config['run_full_model_grid_expansion'] == 'false':
        logging.info("Skipping full model grid expansion as per configuration.")
    else:
        match config['run_full_model_grid_expansion']:
            case 'true':
                logging.info("Running grid expansion planning for the full (unaggregated) model.")
                n_full_grid_expansion = pypsa_model.copy()
                n_full_grid_expansion.generators['p_nom_extendable'] = False  # set all generators to not extendable by default

                # n_full_grid_expansion = data_handling.add_alternative_shortest_path_routes(n_full_grid_expansion, config)

                # Run the optimization for the full model with grid expansion
                n_full_grid_expansion = model_runner.run_model_optimization(n_full_grid_expansion, "full_model_grid_exp", config)

                n_full_grid_expansion.export_to_netcdf(os.path.join(config['results_path'], 'networks', n_full_grid_expansion.name + '.nc'))
                plotting.plot_network_interactive(n_full_grid_expansion, config['results_path'],
                                                  line_color_func=plotting.get_line_colors_by_expansion,
                                                  line_width_func=plotting.get_line_widths_by_expansion,
                                                  transformer_color_func=plotting.get_transformer_colors_by_expansion,
                                                  transformer_width_func=plotting.get_transformer_widths_by_expansion)
                
            case 'presolved':
                n_full_grid_expansion = data_handling.load_network(config, 'full_model_grid_exp_solved.nc')

        model_analyzer.analyze_network_results([n_full_grid_expansion])

    # -------------------------------------------------------------------------
    # 6. Grid Aggregation: NPAP - VA Aggregation
    # -------------------------------------------------------------------------
    if config['aggregate_geo_va'] == 'false':
        logging.info("Skipping geographical, voltage-aware aggregation as per configuration.")
    else:
        match config['aggregate_geo_va']:
            case 'true':
                logging.info("Aggregating the grid using geographical, voltage-aware clustering.")
                n_agg_geo_va, busmap = npap_clustering.aggregate(pypsa_model.copy(), config, 'geo_va_aggregation')

                # n_agg_geo_va = data_handling.add_alternative_shortest_path_routes(n_agg_geo_va, config)
                n_agg_geo_va = model_runner.run_model_optimization(n_agg_geo_va, 'geo_va_aggregation', config)

                n_agg_geo_va.export_to_netcdf(os.path.join(config['results_path'], 'networks', n_agg_geo_va.name + '.nc'))
                plotting.plot_network_interactive(n_agg_geo_va, config['results_path'], 
                                                  line_color_func=plotting.get_line_colors_by_expansion,
                                                  line_width_func=plotting.get_line_widths_by_expansion,
                                                  transformer_color_func=plotting.get_transformer_colors_by_expansion,
                                                  transformer_width_func=plotting.get_transformer_widths_by_expansion)
                plotting.plot_npap_clustering(pypsa_model, config, 'geo_va_aggregation', busmap=busmap)
            case 'presolved':
                n_agg_geo_va = data_handling.load_network(config, 'geo_va_aggregation_solved.nc')
                plotting.plot_npap_clustering(pypsa_model, config, 'geo_va_aggregation')

    # -------------------------------------------------------------------------
    # 7. Grid Aggregation: NPAP - non VA Aggregation
    # -------------------------------------------------------------------------
    if config['aggregate_geo_non_va'] == 'false':
        logging.info("Skipping geographical, non-voltage-aware aggregation as per configuration.")
    else:
        match config['aggregate_geo_non_va']:
            case 'true':
                logging.info("Aggregating the grid using geographical, non-voltage-aware clustering.")
                n_agg_geo_non_va = pypsa_model.copy()

                n_agg_geo_non_va, busmap = npap_clustering.aggregate(n_agg_geo_non_va, config, 'geo_non_va_aggregation')

                n_agg_geo_non_va = model_runner.run_model_optimization(n_agg_geo_non_va, 'geo_non_va_aggregation', config)

                n_agg_geo_non_va.export_to_netcdf(os.path.join(config['results_path'], 'networks', n_agg_geo_non_va.name + '.nc'))
                plotting.plot_network_interactive(n_agg_geo_non_va, config['results_path'], 
                                                  line_color_func=plotting.get_line_colors_by_expansion,
                                                  line_width_func=plotting.get_line_widths_by_expansion,
                                                  transformer_color_func=plotting.get_transformer_colors_by_expansion,
                                                  transformer_width_func=plotting.get_transformer_widths_by_expansion)
                plotting.plot_npap_clustering(pypsa_model, config, 'geo_non_va_aggregation', busmap=busmap)
            case 'presolved':
                n_agg_geo_non_va = data_handling.load_network(config, 'geo_non_va_aggregation_solved.nc')
                plotting.plot_npap_clustering(pypsa_model, config, 'geo_non_va_aggregation')

    # -------------------------------------------------------------------------
    # 9. Grid Aggregation: NPAP - VA Aggregation
    # -------------------------------------------------------------------------
    if config['aggregate_elec_va'] == 'false':
        logging.info("Skipping electrical, voltage-aware aggregation as per configuration.")
    else:
        match config['aggregate_elec_va']:
            case 'true':
                logging.info("Aggregating the grid using electrical distance, voltage-aware clustering.")
                n_agg_elec_va, busmap = npap_clustering.aggregate(pypsa_model.copy(), config, 'elec_va_aggregation')

                # n_agg_elec_va = data_handling.add_alternative_shortest_path_routes(n_agg_elec_va, config)
                n_agg_elec_va = model_runner.run_model_optimization(n_agg_elec_va, 'elec_va_aggregation', config)

                n_agg_elec_va.export_to_netcdf(os.path.join(config['results_path'], 'networks', n_agg_elec_va.name + '.nc'))
                plotting.plot_network_interactive(n_agg_elec_va, config['results_path'], 
                                                  line_color_func=plotting.get_line_colors_by_expansion,
                                                  line_width_func=plotting.get_line_widths_by_expansion,
                                                  transformer_color_func=plotting.get_transformer_colors_by_expansion,
                                                  transformer_width_func=plotting.get_transformer_widths_by_expansion)
                plotting.plot_npap_clustering(pypsa_model, config, 'elec_va_aggregation', busmap=busmap)
            case 'presolved':
                n_agg_elec_va = data_handling.load_network(config, 'elec_va_aggregation_solved.nc')
                plotting.plot_npap_clustering(pypsa_model, config, 'elec_va_aggregation')

    # -------------------------------------------------------------------------
    # 10. Grid Aggregation: NPAP - non VA Aggregation
    # -------------------------------------------------------------------------
    if config['aggregate_elec_non_va'] == 'false':
        logging.info("Skipping electrical, non-voltage-aware aggregation as per configuration.")
    else:
        match config['aggregate_elec_non_va']:
            case 'true':
                logging.info("Aggregating the grid using electrical, non-voltage-aware clustering.")
                n_agg_elec_non_va = pypsa_model.copy()

                n_agg_elec_non_va, busmap = npap_clustering.aggregate(n_agg_elec_non_va, config, 'elec_non_va_aggregation')

                n_agg_elec_non_va = model_runner.run_model_optimization(n_agg_elec_non_va, 'elec_non_va_aggregation', config)

                n_agg_elec_non_va.export_to_netcdf(os.path.join(config['results_path'], 'networks', n_agg_elec_non_va.name + '.nc'))
                plotting.plot_network_interactive(n_agg_elec_non_va, config['results_path'], 
                                                  line_color_func=plotting.get_line_colors_by_expansion,
                                                  line_width_func=plotting.get_line_widths_by_expansion,
                                                  transformer_color_func=plotting.get_transformer_colors_by_expansion,
                                                  transformer_width_func=plotting.get_transformer_widths_by_expansion)
                plotting.plot_npap_clustering(pypsa_model, config, 'elec_non_va_aggregation', busmap=busmap)
            case 'presolved':
                n_agg_elec_non_va = data_handling.load_network(config, 'elec_non_va_aggregation_solved.nc')
                plotting.plot_npap_clustering(pypsa_model, config, 'elec_non_va_aggregation')

    # -------------------------------------------------------------------------
    # 11. Results Analysis & Comparison
    # -------------------------------------------------------------------------
    logging.info("Comparing results between the full model and aggregated versions.")
    model_analyzer.analyze_active_slack_nodes(pypsa_model)
    if (config['run_full_model_grid_expansion'] != 'false'
        and config['aggregate_geo_va'] != 'false'
        and config['aggregate_geo_non_va'] != 'false'
        and config['aggregate_elec_va'] != 'false'
        and config['aggregate_elec_non_va'] != 'false'):
        model_analyzer.analyze_active_slack_nodes(n_agg_geo_va)
        model_analyzer.analyze_active_slack_nodes(n_agg_geo_non_va)
        model_analyzer.analyze_active_slack_nodes(n_agg_elec_va)
        model_analyzer.analyze_active_slack_nodes(n_agg_elec_non_va)
        model_analyzer.analyze_network_results([n_full_grid_expansion, n_agg_geo_va, n_agg_geo_non_va, n_agg_elec_va, n_agg_elec_non_va])
        
        # Summarize investment comparison
        summary_path = os.path.join(config['results_path'], 'investment_comparison_summary.csv')
        model_analyzer.summarize_investment_comparison([n_full_grid_expansion, n_agg_geo_va, n_agg_geo_non_va, n_agg_elec_va, n_agg_elec_non_va], 
                                                        output_path=summary_path)

        # create network collection for statistics
        solved_networks = pypsa.NetworkCollection([n_full_grid_expansion, n_agg_geo_va, n_agg_geo_non_va, n_agg_elec_va, n_agg_elec_non_va])
        expanded_capacity = solved_networks.statistics.expanded_capacity()
        logging.info(expanded_capacity[['Line', 'Transformer']])

        expanded_capex = solved_networks.statistics.expanded_capex()
        logging.info(expanded_capex[['Line', 'Transformer']])

    logging.info("Workflow completed.")


if __name__ == "__main__":
    main()
