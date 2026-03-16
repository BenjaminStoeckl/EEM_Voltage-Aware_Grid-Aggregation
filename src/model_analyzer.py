import logging
import pypsa
import pandas as pd
import os
import json
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

        analysis_row['Added Line Capacity [MVA]'] = line_added_capacity
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


def summarize_investment_comparison(networks: List[pypsa.Network], output_path: Optional[str] = None) -> pd.DataFrame:
    """
    Creates a summary DataFrame comparing investment results across different models.
    The first network in the list is treated as the 'Full Model' baseline for percentage deviations.

    Args:
        networks (List[pypsa.Network]): List of optimized PyPSA networks.
        output_path (Optional[str]): Path to save the summary CSV.

    Returns:
        pd.DataFrame: Summary table of investment metrics.
    """
    summary_data = []
    baseline_line_cost = None
    baseline_trafo_cost = None

    for i, n in enumerate(networks):
        name = getattr(n, 'name', f"Model_{i}")

        # Line investments
        line_added_cap = 0
        line_inv_cost = 0
        line_count = 0
        if not n.lines.empty and 's_nom_opt' in n.lines.columns:
            diff = (n.lines.s_nom_opt - n.lines.s_nom).clip(lower=0)
            invested_mask = diff > 1e-3
            line_count = invested_mask.sum()
            line_added_cap = diff.sum()
            line_inv_cost = (diff * n.lines.capital_cost).sum()

        # Transformer investments
        trafo_added_cap = 0
        trafo_inv_cost = 0
        trafo_count = 0
        if not n.transformers.empty and 's_nom_opt' in n.transformers.columns:
            diff = (n.transformers.s_nom_opt - n.transformers.s_nom).clip(lower=0)
            invested_mask = diff > 1e-3
            trafo_count = invested_mask.sum()
            trafo_added_cap = diff.sum()
            trafo_inv_cost = (diff * n.transformers.capital_cost).sum()

        if i == 0:
            baseline_line_cost = line_inv_cost
            baseline_trafo_cost = trafo_inv_cost

        line_deviation = 0
        if baseline_line_cost is not None and baseline_line_cost != 0:
            line_deviation = (line_inv_cost - baseline_line_cost) / baseline_line_cost * 100

        trafo_deviation = 0
        if baseline_trafo_cost is not None and baseline_trafo_cost != 0:
            trafo_deviation = (trafo_inv_cost - baseline_trafo_cost) / baseline_trafo_cost * 100

        summary_data.append({
            'Model': name,
            'Line Expanded Capacity [GVA]': line_added_cap / 1e3,
            'Line Investment Cost [M€]': line_inv_cost / 1e6,
            'Line Cost Deviation [%]': line_deviation,
            'Invested Lines [#]': line_count,
            'Trafo Expanded Capacity [GVA]': trafo_added_cap / 1e3,
            'Trafo Investment Cost [M€]': trafo_inv_cost / 1e6,
            'Trafo Cost Deviation [%]': trafo_deviation,
            'Invested Transformers [#]': trafo_count
        })

    df = pd.DataFrame(summary_data).set_index('Model')
    df = df.round(2)

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path)
        logging.info(f"Investment comparison summary saved to: {output_path}")
        logging.info("\n" + df.to_string())

    return df


def analyze_voltage_level_investments(networks: List[pypsa.Network], output_path: Optional[str] = None) -> pd.DataFrame:
    """
    Analyzes line investments (added capacity and cost) categorized by voltage levels:
    below 300 kV and 300 kV or above.

    Args:
        networks (List[pypsa.Network]): List of optimized PyPSA networks.
        output_path (Optional[str]): Path to save the summary CSV.

    Returns:
        pd.DataFrame: Summary table of investment metrics split by voltage.
    """
    summary_data = []

    for i, n in enumerate(networks):
        name = getattr(n, 'name', f"Model_{i}")

        added_cap_low = 0
        cost_low = 0
        added_cap_high = 0
        cost_high = 0

        if not n.lines.empty and 's_nom_opt' in n.lines.columns:
            # Get line voltages based on bus0
            line_v_nom = n.lines.bus0.map(n.buses.v_nom)

            # Line investments
            diff = (n.lines.s_nom_opt - n.lines.s_nom).clip(lower=0)
            costs = diff * n.lines.capital_cost

            mask_low = line_v_nom < 300
            mask_high = line_v_nom >= 300

            added_cap_low = diff[mask_low].sum()
            cost_low = costs[mask_low].sum()

            added_cap_high = diff[mask_high].sum()
            cost_high = costs[mask_high].sum()

        summary_data.append({
            'Model': name,
            'Low-V Added Capacity (<300kV) [MVA]': added_cap_low,
            'Low-V Investment Cost [€]': cost_low,
            'High-V Added Capacity (>=300kV) [MVA]': added_cap_high,
            'High-V Investment Cost [€]': cost_high,
            'Total Added Line Capacity [MVA]': added_cap_low + added_cap_high,
            'Total Line Investment Cost [€]': cost_low + cost_high
        })

    df = pd.DataFrame(summary_data).set_index('Model')
    df = df.round(2)

    logging.info("\nVoltage-Level Investment Analysis (Lines):")
    logging.info(df.to_string())

    if output_path:
        directory = os.path.dirname(output_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        file_path = os.path.join(directory, 'comparison_investment_by_voltage.csv')
        df.to_csv(file_path)
        logging.info(f"Voltage-level investment analysis saved to: {file_path}")

    return df


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


def generate_investment_latex_table(
    networks: List[pypsa.Network],
    investment_df: pd.DataFrame,
    config: dict,
    template_path: str = 'latex_templates/investment_cost_results_latex_table.txt',
):
    """
    Fills a LaTeX template with investment summary data from a DataFrame.

    This function takes a DataFrame, typically from `summarize_investment_comparison`,
    and uses it to fill placeholders in a specified LaTeX template. It persists the
    placeholder values in a JSON file within the output directory, allowing for
    cumulative updates over multiple runs.

    Args:
        networks (List[pypsa.Network]): List of networks to get node counts from.
        investment_df (pd.DataFrame): DataFrame containing investment summary data.
        config (dict): The configuration dictionary.
        template_path (str): Path to the LaTeX template file.
    """
    output_dir: str = config['results_path']
    os.makedirs(output_dir, exist_ok=True)

    # Manage placeholder dictionary for persistence
    placeholder_path = os.path.join(output_dir, 'latex_placeholders.json')
    if os.path.exists(placeholder_path):
        with open(placeholder_path, 'r') as f:
            placeholders = json.load(f)
    else:
        placeholders = {}

    # Create a map from model name to its bus count
    bus_counts = {n.name: len(n.buses) for n in networks}

    # Update placeholders from the input DataFrame
    for model_name, row in investment_df.iterrows():
        key_prefix = None
        # Improved name parsing
        if model_name.startswith('full_model_grid_exp'):
            key_prefix = 'FG'
        elif 'geo_va_aggregation' in model_name:
            num_clusters = config.get('geo_va_aggregation', {}).get('num_of_clusters')
            if num_clusters:
                key_prefix = f'VA_{num_clusters}'
        elif 'geo_non_va_aggregation' in model_name:
            num_clusters = config.get('geo_non_va_aggregation', {}).get('num_of_clusters')
            if num_clusters:
                key_prefix = f'VU_{num_clusters}'

        if not key_prefix:
            logging.debug(f"Model name '{model_name}' not configured for LaTeX table. Skipping.")
            continue

        # Add k value to placeholders (only if a placeholder like @@K_FG@@ exists in template)
        bus_count = bus_counts.get(model_name)
        if bus_count is not None:
            placeholders[f'@@K_{key_prefix}@@'] = str(bus_count)

        # Update placeholders for lines and transformers
        for component in ['Line', 'Trafo']:
            cap_gva = row.get(f'{component} Expanded Capacity [GVA]', 'N/A')
            cost_meur = row.get(f'{component} Investment Cost [M€]', 'N/A')
            cost_dev = row.get(f'{component} Cost Deviation [%]')

            comp_key = 'LINES' if component == 'Line' else 'TRAFO'

            if cap_gva != 'N/A':
                placeholders[f'@@{comp_key}_{key_prefix}_CAP@@'] = f"{cap_gva:.1f}"
            if cost_meur != 'N/A':
                placeholders[f'@@{comp_key}_{key_prefix}_COST@@'] = f"{cost_meur:.1f}"

            if cost_dev is not None and not pd.isna(cost_dev):
                relative_perc = 100 + cost_dev
                placeholders[f'@@{comp_key}_{key_prefix}_PERC@@'] = f"{relative_perc:.1f}\\%"
            # elif key_prefix == 'FG':
            #     placeholders[f'@@{comp_key}_{key_prefix}_PERC@@'] = "100.0\\%"

    # Save updated placeholder dictionary
    with open(placeholder_path, 'w') as f:
        json.dump(placeholders, f, indent=4, sort_keys=True)
    logging.info(f"Updated LaTeX placeholders saved to {placeholder_path}")

    # Load template and fill placeholders
    try:
        with open(template_path, 'r') as f:
            template_content = f.read()
    except FileNotFoundError:
        logging.error(f"LaTeX template not found at: {template_path}")
        return

    filled_template = template_content
    for key, value in placeholders.items():
        filled_template = filled_template.replace(str(key), str(value))

    # Save filled LaTeX table
    output_latex_path = os.path.join(output_dir, 'investment_cost_summary.tex')
    with open(output_latex_path, 'w') as f:
        f.write(filled_template)
    logging.info(f"Filled LaTeX table saved to {output_latex_path}")