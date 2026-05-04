import logging
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

        # 2. Total production and storage sums (MW summed over 1h snapshots = MWh)
        gen_total = 0
        if not n.generators_t.p.empty:
            gen_total = n.generators_t.p.sum().sum()
            generator_production = n.generators_t.p.sum().groupby(n.generators.carrier).sum()
            for carrier, total_production in generator_production.items():
                analysis_row[f'Production ({carrier}) [MWh]'] = total_production

        discharge_total = 0
        charge_total = 0
        if not n.storage_units_t.p.empty:
            # p > 0 is discharging (acting as a generator)
            discharge_total = n.storage_units_t.p[n.storage_units_t.p > 0].sum().sum()

            # p < 0 is charging (acting as a load). We take the absolute value for reporting.
            charge_total = abs(n.storage_units_t.p[n.storage_units_t.p < 0].sum().sum())

            storage_discharge = n.storage_units_t.p[n.storage_units_t.p > 0].sum().groupby(n.storage_units.carrier).sum()
            for carrier, total_production in storage_discharge.items():
                analysis_row[f'Production (Storage Discharge {carrier}) [MWh]'] = total_production

        # Log system totals
        analysis_row['Total Generator Production [MWh]'] = gen_total
        analysis_row['Total Storage Discharge [MWh]'] = discharge_total
        analysis_row['Gross System Production (Gen + Discharge) [MWh]'] = gen_total + discharge_total
        analysis_row['Total Storage Charge [MWh]'] = charge_total

        # 3. Curtailed energy, non-supplied energy, and total demand
        total_original_load_demand = 0
        total_served_load = 0
        if not n.loads_t.p.empty:
            if hasattr(n.loads_t, 'p_set'):
                total_original_load_demand = n.loads_t.p_set.sum().sum()
            else:
                total_original_load_demand = (n.loads.p_set * len(n.snapshots)).sum()

            total_served_load = n.loads_t.p.sum().sum()

            analysis_row['Total Demand [MWh]'] = total_original_load_demand
            analysis_row['Gross System Consumption (Demand + Charge) [MWh]'] = total_original_load_demand + charge_total
            analysis_row['Non-Supplied Energy (Unmet Load) [MWh]'] = max(0, total_original_load_demand - total_served_load)
        else:
            analysis_row['Total Demand [MWh]'] = 0
            analysis_row['Gross System Consumption (Demand + Charge) [MWh]'] = charge_total
            analysis_row['Non-Supplied Energy (Unmet Load) [MWh]'] = 0

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

        # 4. Line Investments (Capacity added and Cost)
        line_added_capacity = 0
        line_investment_cost = 0
        if not n.lines.empty and 's_nom_extendable' in n.lines.columns:
            if n.lines.s_nom_extendable.any():
                extendable_lines = n.lines[n.lines.s_nom_extendable]
                added_capacity = (extendable_lines.s_nom_opt - extendable_lines.s_nom)

                line_added_capacity = added_capacity.sum()
                line_investment_cost = (added_capacity * extendable_lines.capital_cost).sum()

                added_lines_length = extendable_lines.length
                added_capacity_length = (added_capacity * added_lines_length).sum()


        analysis_row['Added Line Capacity [MVA]'] = line_added_capacity
        analysis_row['Added Line Capacity x Length [MVA*km]'] = added_capacity_length
        analysis_row['Line Investment Cost [€]'] = line_investment_cost

        # 5. Transformer Investments (Capacity added and Cost)
        trafo_added_capacity = 0
        trafo_investment_cost = 0
        if not n.transformers.empty and 's_nom_extendable' in n.transformers.columns:
            if n.transformers.s_nom_extendable.any():
                extendable_trafos = n.transformers[n.transformers.s_nom_extendable]
                added_capacity = (extendable_trafos.s_nom_opt - extendable_trafos.s_nom)

                trafo_added_capacity = added_capacity.sum()
                trafo_investment_cost = (added_capacity * extendable_trafos.capital_cost).sum()

        analysis_row['Added Transformer Capacity [MVA]'] = trafo_added_capacity
        analysis_row['Transformer Investment Cost [€]'] = trafo_investment_cost

        # 6. Total Grid Expansion
        analysis_row['Total Added Grid Capacity [MVA]'] = line_added_capacity + trafo_added_capacity
        analysis_row['Total Grid Investment Cost [€]'] = line_investment_cost + trafo_investment_cost

        results_data.append(analysis_row)

    # Convert to DataFrame
    results_df = pd.DataFrame(results_data)

    # Round all numeric values to 2 decimals
    results_df = results_df.round(2)

    logging.info("\nAnalyzed Network Results (Summed over all snapshots):")
    # Set 'Network' as index and transpose for desired output format
    formatted_output_df = results_df.set_index('Network').T
    logging.info(formatted_output_df.to_string())

    # Export to CSV if output_path is provided
    if output_path:
        directory = os.path.dirname(output_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        results_df.to_csv(output_path, index=False)
        logging.info(f"Analysis results exported to: {output_path}")

    return results_df


def analyze_active_slack_nodes(n: pypsa.Network) -> pd.Series:
    """
    Identifies buses where slack generators are producing non-zero power
    and calculates the total production sum for each of those nodes.

    Args:
        n (pypsa.Network): The optimized PyPSA network.

    Returns:
        pd.Series: Total slack production indexed by bus name.
    """
    # 1. Identify which generators are 'slack'
    slack_gen_mask = n.generators.carrier == "slack"
    slack_gens = n.generators[slack_gen_mask]

    if slack_gens.empty or n.generators_t.p.empty:
        logging.info("No slack generators found or no production data available.")
        return pd.Series(dtype=float)

    # 2. Get the time-series production (p) for only the slack generators
    slack_p = n.generators_t.p[slack_gens.index]

    # 3. Calculate the total sum over all snapshots for each generator
    slack_totals = slack_p.sum()

    # 4. Filter for only those that are actually producing (sum > 0)
    active_slack_totals = slack_totals[slack_totals > 1e-3]  # Use small epsilon for float precision

    if active_slack_totals.empty:
        logging.info("No active slack production detected (All slack generators are at 0).")
        return pd.Series(dtype=float)

    # 5. Map the generator names back to their respective buses
    # We group by bus in case a single bus has multiple slack generators
    active_slack_df = pd.DataFrame({
        'production': active_slack_totals,
        'bus': n.generators.loc[active_slack_totals.index, 'bus']
    })

    bus_slack_summary = active_slack_df.groupby('bus')['production'].sum()

    logging.info("\n--- Active Slack Production by Node ---")
    for bus, val in bus_slack_summary.items():
        if val > 0.1:  # Only print significant slack production
            logging.info(f"Bus {bus}: {val:.2f} MWh")

    logging.info(f"Total System-wide Slack Production: {bus_slack_summary.sum():.2f} MWh")

    return bus_slack_summary