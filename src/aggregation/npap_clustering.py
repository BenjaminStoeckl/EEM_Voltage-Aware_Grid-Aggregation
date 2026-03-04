"""
Placeholder module for the custom voltage-aware grid aggregation method.
"""
import pypsa
from pypsa.clustering.npap import npap_clustering
from pypsa.clustering.spatial import DEFAULT_ONE_PORT_STRATEGIES


def aggregate(n: pypsa.Network, va_aggregation_config: dict, line_strategies: dict, transformer_strategies: dict = None) -> pypsa.Network:
    """
    A placeholder for the voltage-aware aggregation method.

    This function will eventually contain the logic for your custom
    aggregation technology.

    Args:
        n (pypsa.Network): The network to be aggregated.
        va_aggregation_config: configuration for voltage-aware aggregation, e.g., {'num_of_clusters': 100, 'strategy': 'va_electrical_kmedoids'}.
        line_strategies: strategies for aggregating line attributes.
        transformer_strategies: strategies for aggregating transformer attributes.


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
        line_strategies=line_strategies,
        transformer_strategies=transformer_strategies,
    )

    network = result.n

    # Map s_nom_extendable from original network to aggregated network
    if 's_nom_extendable' in n.lines.columns:
        # Aggregated line is extendable if any original line in the cluster was extendable
        extendable_any = n.lines.s_nom_extendable.groupby(result.linemap).any()
        network.lines['s_nom_extendable'] = False
        network.lines.loc[extendable_any.index, 's_nom_extendable'] = extendable_any

    network.name = 'model_agg_npap'
    network.sanitize()

    return network
