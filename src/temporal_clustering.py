"""
Module for temporal (time-series) clustering of the network.
"""
from typing import Dict, Optional

import pandas as pd
import pypsa
import tsam.timeseriesaggregation as tsam
from pypsa.clustering.temporal import downsample, from_snapshot_map


def aggregate_temporally_by_downsampling(n: pypsa.Network, temporal_config: Dict) -> pypsa.Network:
    """
    Performs temporal clustering on the network's time series data.

    This function will reduce the number of snapshots to a set of representative
    periods, which makes the optimization problem easier to solve.

    Args:
        n (pypsa.Network): The PyPSA network with full time series.
        temporal_config (Dict): A dictionary containing clustering parameters,
                                e.g., {'n_timestep_clusters': 10}.

    Returns:
        pypsa.Network: A new network object with clustered time series.
    """
    print(f"Performing temporal clustering to {temporal_config['n_timestep_clusters']} periods...")
    # The actual clustering logic will be implemented here.
    # For now, we'll just return the network as is.
    # A typical implementation would use tsam or pypsa.clustering.

    clustered = downsample(n, int(len(n.snapshots) / temporal_config['n_timestep_clusters']))

    return clustered.n


def create_snapshot_series_from_temporal_clustering(
    n: pypsa.Network,
    temporal_clustering_config: Dict,
    time_series_component: Optional[str] = "net_load"
) -> pd.Series:
    """
    Creates a snapshot series by temporally clustering snapshots based on the
    similarity of their network-wide time series profiles (e.g., total net load)
    using tsam's k-means clustering.

    Args:
        n (pypsa.Network): The PyPSA network.
        temporal_clustering_config (Dict): Configuration for temporal clustering,
                                           e.g., {'n_clusters': 5}.
        time_series_component (str): The time series component(s) to use for
                                     clustering snapshots. Options: 'demand', 'renewables', or 'net_load' (to include both demand and renewables).
                                     Defaults to 'net_load'.

    Returns:
        pd.Series: A Series mapping original snapshots to cluster IDs.
                   The index contains original snapshots, and values are
                   the cluster IDs (integers or strings).
    """
    n_clusters = temporal_clustering_config['n_timestep_clusters']
    print(f"Clustering snapshots into {n_clusters} groups based on aggregated network {time_series_component} time series...")

    # 1. Extract relevant time series for the entire network
    # The time_series_component parameter will now dictate which specific combination
    # of time series to include in the clustering DataFrame.
    network_time_series_data = {}

    if "net_load" in time_series_component or "demand" in time_series_component:
        total_demand = pd.Series(0.0, index=n.snapshots)
        if not n.loads.empty:
            total_demand = n.loads_t.p_set.sum(axis=1)
        network_time_series_data['demand'] = total_demand

    if "net_load" in time_series_component or "renewables" in time_series_component:
        total_renewable_generation = pd.Series(0.0, index=n.snapshots)
        # Assuming common renewable carriers. This list might need adjustment
        # depending on the specific PyPSA network data.
        renewable_carriers = ['wind', 'solar', 'hydro', 'solar_rooftop']

        if not n.generators.empty:
            renewable_generators = n.generators[n.generators.carrier.isin(renewable_carriers)]
            if not renewable_generators.empty:
                total_renewable_generation = (
                    n.generators_t.p_max_pu[renewable_generators.index]
                    .sum(axis=1)
                )
        network_time_series_data['renewables'] = total_renewable_generation

    if not network_time_series_data:
        raise ValueError(f"Unsupported or empty time_series_component: {time_series_component}. "
                         "Must include 'demand' or 'renewables' or 'net_load'.")

    network_time_series_df = pd.DataFrame(network_time_series_data)

    # If the user specified 'net_load' for time_series_component, we will still cluster on
    # individual 'demand' and 'renewables' series as features.
    # If a single 'net_load' series was desired, the previous implementation should be used.
    # The current interpretation is to provide features for a more nuanced temporal clustering.

    # 2. Perform tsam K-Means Clustering on the network time series
    aggregation = tsam.TimeSeriesAggregation(
        network_time_series_df,
        noTypicalPeriods=n_clusters,
        clusterMethod='k_means',
        representationMethod='meanRepresentation',
    )

    mapping = aggregation.indexMatching()

    cluster_labels = "P_" + mapping['PeriodNum'].astype(str) + "_H_" + mapping['TimeStep'].astype(str)

    # PyPSA requires a Pandas Series: Index = original snapshots, Values = new cluster labels
    snapshot_clustering = pd.Series(cluster_labels.values, index=n.snapshots)

    return snapshot_clustering


def aggregate_temporally_by_clustering(n: pypsa.Network, config: dict) -> pypsa.Network:
    """
    Performs temporal aggregation of the network based on snapshot clustering derived
    from network-wide time series similarity.

    This function first clusters snapshots using `create_snapshot_series_from_temporal_clustering`
    to identify representative periods based on aggregated network time series (e.g., net load).
    It then applies this snapshot mapping to the network to aggregate components based on
    these temporal clusters, reducing the network's complexity.

    Args:
        n (pypsa.Network): The PyPSA network to be aggregated.
        config (dict): Configuration dictionary for the temporal clustering, which
                       will be passed to `create_snapshot_series_from_temporal_clustering`.
                       Expected to contain 'n_clusters' among other parameters.

    Returns:
        pypsa.Network: The aggregated PyPSA network.
    """

    if config['clustering_strategy'] == 'downsampling':
        print("Using downsampling for temporal aggregation.")
        return aggregate_temporally_by_downsampling(n, config)
    elif config['clustering_strategy'] == 'kmeans':
        print("Using k-means clustering for temporal aggregation.")
        # get snapshot_cluster_series from temporal clustering
        snapshot_cluster_series = create_snapshot_series_from_temporal_clustering(n, temporal_clustering_config=config)
        clustered = from_snapshot_map(n, snapshot_cluster_series)
        return clustered.n
    else:
        raise ValueError(f"Unsupported clustering strategy: {config['clustering_strategy']}, Use: 'downsampling' or 'kmeans'.")
