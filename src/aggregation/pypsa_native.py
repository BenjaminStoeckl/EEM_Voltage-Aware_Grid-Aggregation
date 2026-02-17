"""
Module for grid aggregation using native PyPSA clustering methods.
"""
import pypsa
from typing import Dict

from pypsa.clustering.spatial import DEFAULT_ONE_PORT_STRATEGIES


def aggregate(n: pypsa.Network, aggregation_options: Dict) -> pypsa.Network:
    """
    Aggregates the grid using PyPSA's built-in network clustering.

    This implementation uses a geographical strategy based on bus coordinates.

    Args:
        n (pypsa.Network): The PyPSA network to be aggregated.
        aggregation_options (Dict): Configuration for the clustering strategies.

    Returns:
        pypsa.Network: The aggregated network.
    """
    print("Aggregating network with native PyPSA geographical clustering...")
    
    # The actual aggregation logic will be implemented here.
    # This is a placeholder for the PyPSA function call.
    # Example using pypsa.networkclustering:
    # aggregated_n = pypsa.networkclustering.cluster_network(n, **aggregation_options)
    
    # For now, we return a simplified representation of the network
    print("PyPSA native aggregation not yet fully implemented. Returning a simplified network.")
    
    # Create a dummy aggregated network for workflow testing
    n_agg = pypsa.Network()
    n_agg.add("Bus", "AggregatedBus")
    n_agg.set_snapshots(n.snapshots) # Keep the same snapshots
    
    return n_agg


def aggregate_stubs(n: pypsa.Network) -> pypsa.Network:
    """
    Aggregates 'stub' buses and their associated components in the network.

    This function uses PyPSA's spatial clustering to reduce buses that are
    considered 'stubs' (e.g., isolated buses or those with limited connections)
    by mapping them to existing buses based on specified attributes.
    It applies predefined strategies for aggregating bus and line attributes
    and re-attaches transformers to the resulting clustered network.

    Args:
        n (pypsa.Network): The PyPSA network to be processed for stub aggregation.

    Returns:
        pypsa.Network: The network with stub buses aggregated.
    """


    reduce_stub_bus_strategie = {
        'symbol': 'first',
        'tags': 'first',
        'country': 'first',
        'substation_lv': 'first',
        'substation_off': 'first',
        'control': 'first',
    }

    reduce_stub_lines_strategie = {
        'underground': 'first',
        'under_construction': 'first',
        'tags': 'first',
        'geometry': 'first',
    }

    reduce_stub_busmap = pypsa.clustering.spatial.busmap_by_stubs(n, ['carrier', 'v_nom', 'under_construction'])

    clustering = pypsa.clustering.spatial.get_clustering_from_busmap(n,
                                                                     reduce_stub_busmap,
                                                                     bus_strategies=reduce_stub_bus_strategie,
                                                                     line_strategies=reduce_stub_lines_strategie,
                                                                     one_port_strategies=DEFAULT_ONE_PORT_STRATEGIES,
                                                                     aggregate_one_ports=["Generator", "Load", "StorageUnit"]
                                                                     )

    clustered_network = clustering.n
    clustered_network.transformers = n.transformers  # add transformers because they are not handled by the clustering

    return clustering.n
