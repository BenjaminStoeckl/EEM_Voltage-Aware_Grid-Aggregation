"""
Module for temporal (time-series) clustering of the network.
"""
from typing import Dict

import pypsa

from pypsa.clustering.temporal import downsample


def cluster_temporally(n: pypsa.Network, temporal_config: Dict) -> pypsa.Network:
    """
    Performs temporal clustering on the network's time series data.

    This function will reduce the number of snapshots to a set of representative
    periods, which makes the optimization problem easier to solve.

    Args:
        n (pypsa.Network): The PyPSA network with full time series.
        temporal_config (Dict): A dictionary containing clustering parameters,
                                e.g., {'n_clusters': 10}.

    Returns:
        pypsa.Network: A new network object with clustered time series.
    """
    print(f"Performing temporal clustering to {temporal_config['n_clusters']} periods...")
    # The actual clustering logic will be implemented here.
    # For now, we'll just return the network as is.
    # A typical implementation would use tsam or pypsa.clustering.

    return downsample(n, len(n.snapshots)/temporal_config['n_clusters'])
