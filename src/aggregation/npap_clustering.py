"""
Placeholder module for the custom voltage-aware grid aggregation method.
"""
import logging
import numpy as np
import pandas as pd
import pypsa
from pypsa.clustering.npap import npap_clustering
from pypsa.clustering.spatial import DEFAULT_ONE_PORT_STRATEGIES


def _derive_transformer_mapping(n_orig: pypsa.Network, n_agg: pypsa.Network, busmap: pd.Series) -> pd.Series:
    """
    Identifies which original transformers correspond to which aggregated transformers
    by comparing their terminal buses after mapping them through the busmap.

    Returns a Series mapping original transformer indices to aggregated transformer indices.
    """
    if n_orig.transformers.empty or n_agg.transformers.empty:
        return pd.Series(dtype=object)

    def get_canonical_keys(df, bmap=None):
        # Map buses if a busmap is provided
        b0 = df.bus0.map(bmap) if bmap is not None else df.bus0
        b1 = df.bus1.map(bmap) if bmap is not None else df.bus1
        
        # Ensure they are strings for concatenation
        b0, b1 = b0.astype(str), b1.astype(str)
        
        # Create a sorted key so order doesn't matter (u-v is same as v-u)
        mask = b0 > b1
        return np.where(mask, b1 + "-" + b0, b0 + "-" + b1)

    # Calculate keys for original transformers (mapped to new buses) and aggregated transformers
    orig_keys = pd.Series(get_canonical_keys(n_orig.transformers, busmap), index=n_orig.transformers.index)
    agg_keys = pd.Series(get_canonical_keys(n_agg.transformers), index=n_agg.transformers.index)
    
    # Map aggregated keys to their indices. drop_duplicates handles parallel branches if they exist.
    key_to_agg_idx = pd.Series(agg_keys.index, index=agg_keys.values).drop_duplicates()
    
    return orig_keys.map(key_to_agg_idx)


def aggregate(n: pypsa.Network, config: dict, label: str) -> pypsa.Network:
    """
    A placeholder for the voltage-aware aggregation method.

    This function will eventually contain the logic for your custom
    aggregation technology.

    Args:
        n (pypsa.Network): The network to be aggregated.
        config (dict): The complete configuration dictionary.
        label (str): The label identifying which aggregation settings to use from the config (e.g., 'geo_va_aggregation').

    Returns:
        pypsa.Network: The aggregated network.
    """

    va_aggregation_config = config[label]
    line_strategies = config.get('line_strategies', {})
    transformer_strategies = config.get('transformer_strategies', {})

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
        logging.info(f"Mapped 's_nom_extendable' for {len(extendable_any)} aggregated lines based on original line data.")

    # Map s_nom_extendable for transformers
    if 's_nom_extendable' in n.transformers.columns and not network.transformers.empty:
        # Since npap_clustering doesn't return a direct trafomap, derive it from the busmap
        traftomap = _derive_transformer_mapping(n, network, result.busmap)
        valid_traftomap = traftomap.dropna()
        
        if not valid_traftomap.empty:
            extendable_any_trafo = n.transformers.s_nom_extendable.loc[valid_traftomap.index].groupby(valid_traftomap).any()
            network.transformers['s_nom_extendable'] = False
            network.transformers.loc[extendable_any_trafo.index, 's_nom_extendable'] = extendable_any_trafo
            logging.info(f"Mapped 's_nom_extendable' for {len(extendable_any_trafo)} aggregated transformers based on original transformer data.")

    network.name = 'model_agg_npap'
    network.sanitize()

    return network
