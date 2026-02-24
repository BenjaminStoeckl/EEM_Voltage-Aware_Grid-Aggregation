import pypsa
import pandas as pd
import os
from typing import List, Optional


def analyze_network_results(networks: List[pypsa.Network], output_path: Optional[str] = None) -> pd.DataFrame:
    """
    Analyzes the results of one or multiple PyPSA networks, providing key metrics
    such as objective function value, total production sums by technology,
    and information about curtailed and non-supplied energy over all snapshots.

    Args:
        networks (List[pypsa.Network]): A list of PyPSA network objects to analyze.
                                        Each network is expected to have been optimized.
        output_path (Optional[str]): An optional file path to export the analysis
                                     results to a .csv file. If None, results are not exported.

    Returns:
        pd.DataFrame: A DataFrame containing the analysis results for each network.
                      Each row corresponds to a network, and columns represent the metrics.
    """
    results_data = []

    for i, n in enumerate(networks):
        network_name = getattr(n, 'name', f"Network_{i}")
        analysis_row = {'Network': network_name}

        # 1. Objective function value (PyPSA default is usually €)
        analysis_row['Objective Function Value [€]'] = n.objective

        # 2. Total production sums (MW summed over 1h snapshots = MWh)
        if not n.generators_t.p.empty:
            generator_production = n.generators_t.p.sum().groupby(n.generators.carrier).sum()
            for carrier, total_production in generator_production.items():
                analysis_row[f'Production ({carrier}) [MWh]'] = total_production

        if not n.storage_units_t.p.empty:
            storage_discharge = n.storage_units_t.p[n.storage_units_t.p > 0].sum().groupby(n.storage_units.carrier).sum()
            for carrier, total_production in storage_discharge.items():
                analysis_row[f'Production (Storage Discharge {carrier}) [MWh]'] = total_production

        # 3. Curtailed energy and non-supplied energy
        total_original_load_demand = 0
        total_served_load = 0
        if not n.loads_t.p.empty:
            if hasattr(n.loads_t, 'p_set'):
                total_original_load_demand = n.loads_t.p_set.sum().sum()
            else:
                total_original_load_demand = (n.loads.p_set * len(n.snapshots)).sum()

            total_served_load = n.loads_t.p.sum().sum()
            analysis_row['Non-Supplied Energy (Unmet Load) [MWh]'] = max(0, total_original_load_demand - total_served_load)

        # Renewable curtailment
        renewable_carriers = ['wind', 'solar', 'pv']
        renewable_generators = n.generators[n.generators.carrier.isin(renewable_carriers)]

        if not renewable_generators.empty and not n.generators_t.p.empty:
            available_renewable_production = (
                n.generators_t.p_max_pu[renewable_generators.index] *
                renewable_generators.p_nom
            ).sum().sum()

            actual_renewable_production = n.generators_t.p[renewable_generators.index].sum().sum()

            analysis_row['Renewable Curtailment [MWh]'] = max(0, available_renewable_production - actual_renewable_production)
        else:
            analysis_row['Renewable Curtailment [MWh]'] = 0

        results_data.append(analysis_row)

    # Convert to DataFrame
    results_df = pd.DataFrame(results_data)

    # Round all numeric values to 2 decimals
    results_df = results_df.round(2)

    print("\nAnalyzed Network Results (Summed over all snapshots):")
    # Set 'Network' as index and transpose for desired output format
    formatted_output_df = results_df.set_index('Network').T
    print(formatted_output_df.to_string())

    # Export to CSV if output_path is provided
    if output_path:
        directory = os.path.dirname(output_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        results_df.to_csv(output_path, index=False)
        print(f"Analysis results exported to: {output_path}")

    return results_df