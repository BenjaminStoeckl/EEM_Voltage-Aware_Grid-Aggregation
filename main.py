"""
Main script to run the grid aggregation testing framework.
"""

import yaml
import pypsa
import logging

from src import data_handling, temporal_clustering, model_runner, postprocessing, plotting
from src.aggregation import pypsa_native, voltage_aware

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    """
    Orchestrates the entire workflow for comparing grid aggregation methods.
    """
    # 0. Load configuration
    logging.info("Loading configuration from config.yaml")
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    # 1. Load a plottable PyPSA example network
    logging.info("Loading ac_dc_meshed example network.")
    n_full = pypsa.examples.scigrid_de()

    # 2. Plot the initial grid setup for verification
    plotting.plot_network(n_full, config['results_path'])


    # 3. Cluster the test case temporally
    logging.info(f"Clustering network temporally to {config['temporal_clustering']['n_clusters']} periods.")
    n_clustered = temporal_clustering.cluster_temporally(n_full, config['temporal_clustering'])

    # # 3. Configure and run the full, but temporally clustered, model for expansion planning
    # logging.info("Running expansion planning for the full (unaggregated) model.")
    # full_model_results_path = model_runner.run_expansion_planning(
    #     n_clustered.copy(), "full_model", config
    # )
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
