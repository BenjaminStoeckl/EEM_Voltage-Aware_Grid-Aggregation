"""
Placeholder module for the custom voltage-aware grid aggregation method.
"""
import pypsa
from typing import Dict
from pypsa.clustering.npap import npap_clustering
from pypsa.clustering.spatial import DEFAULT_ONE_PORT_STRATEGIES


def aggregate(n: pypsa.Network, va_aggregation_config: dict) -> pypsa.Network:
    """
    A placeholder for the voltage-aware aggregation method.

    This function will eventually contain the logic for your custom
    aggregation technology.

    Args:
        n (pypsa.Network): The network to be aggregated.
        va_aggregation_config: configuration for voltage-aware aggregation, e.g., {'num_of_clusters': 100, 'strategy': 'va_electrical_kmedoids'}.


    Raises:
        NotImplementedError: This function is not yet implemented.

    Returns:
        pypsa.Network: The aggregated network.
         """

    my_strategies = {
        **DEFAULT_ONE_PORT_STRATEGIES,
        "p_dispatch": "sum",
        "p_store": "sum",
        "state_of_charge": "sum",
        "spill": "sum",
    }


    result = npap_clustering(
        n,
        n_clusters=va_aggregation_config['num_of_clusters'],
        strategy=va_aggregation_config['strategy'],
        include_transformers=True,
        include_links=True,
        voltage_levels=[220, 380],
        line_strategies=va_aggregation_config['line_strategies'],
    )

    network = result.n
    network.name = 'model_agg_npap'
    # network.lines['under_construction'] = 0  # Ensure no lines are marked as under construction after aggregation
    network.sanitize()

    return network

