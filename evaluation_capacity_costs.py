
import os
import pypsa
import pandas as pd
import logging

from xarray.core.indexing import expanded_indexer

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Base directory where results are stored
# The user can add multiple case directories here
CASE_DIRS = [
    r"C:\BeSt\VA-GA\WS-results\FM_agg250_no_stub_agg_yanwe_exp_heur",
    r"C:\BeSt\VA-GA\WS-results\FM_agg500_no_stub_agg_yanwe_exp_heur",
    r"C:\BeSt\VA-GA\WS-results\FM_agg1000_no_stub_agg_yanwe_exp_heur",
    r"C:\BeSt\VA-GA\WS-results\FM_agg3000_no_stub_agg_yanwe_exp_heur",
    # Add more paths as needed
]

OUTPUT_BASE_DIR = r"C:\BeSt\VA-GA\WS-results\analysis_results"

# Network files and their settings within each case's "networks" folder:
# (filename, display_name, voltage_aware)
NETWORKS_TO_LOAD = [
    ("full_model_grid_exp_solved.nc",       "full_model_grid_exp",     True),
    ("geo_va_aggregation_solved.nc",        "geo_va_aggregation",      True),
    ("geo_non_va_aggregation_solved.nc",    "geo_non_va_aggregation",  False),
    # ("elec_va_aggregation_solved.nc",       "elec_va_aggregation",     True),
    # ("elec_non_va_aggregation_solved.nc",   "elec_non_va_aggregation", False),
]

# ---------------------------------------------------------------------------
# Analysis Function
# ---------------------------------------------------------------------------
def extract_expansion_metrics(n: pypsa.Network, voltage_aware: bool):
    """
    Extracts expansion metrics from a solved PyPSA network.
    
    Returns a dictionary with:
    - total_invested_capacity [MVA]
    - total_expanded_length [km]
    - total_expansion_cost [€]
    - (if voltage_aware) split versions of the above for >300kV and <=300kV
    """
    if n.lines.empty or 's_nom_extendable' not in n.lines:
        return {}

    # We only care about lines where expansion was possible (s_nom_extendable)
    # and where expansion actually occurred (s_nom_opt > s_nom)
    extendable = n.lines.s_nom_extendable
    # Calculate added capacity, ensuring it's not negative
    added_cap = (n.lines.s_nom_opt - n.lines.s_nom).clip(lower=0)
    
    # Mask for lines that actually expanded (using a small epsilon for float comparison)
    expanded_mask = (added_cap > 1e-3) & extendable
    
    if not expanded_mask.any():
        return {
            "invested_capacity": 0,
            "expanded_length": 0,
            "expansion_cost": 0,
        }

    expanded_lines = n.lines[expanded_mask]
    added_cap_expanded = added_cap[expanded_mask]
    costs = (added_cap_expanded * expanded_lines.capital_cost)
    lengths = expanded_lines.length
    expanded_cap_length = added_cap_expanded * lengths
    
    metrics = {
        "invested_capacity": added_cap_expanded.sum(),
        "expanded_length": lengths.sum(),
        "expansion_cost": costs.sum(),
        "expanded_cap_length": expanded_cap_length.sum(),
    }

    if voltage_aware:
        # Split analysis based on nominal voltage (v_nom is in kV)
        over_300kv_mask = expanded_lines.v_nom > 300
        under_300kv_mask = ~over_300kv_mask
        
        metrics.update({
            "invested_capacity > 300kV": added_cap_expanded[over_300kv_mask].sum(),
            "invested_capacity <= 300kV": added_cap_expanded[under_300kv_mask].sum(),
            "expanded_length > 300kV": lengths[over_300kv_mask].sum(),
            "expanded_length <= 300kV": lengths[under_300kv_mask].sum(),
            "expansion_cost > 300kV": costs[over_300kv_mask].sum(),
            "expansion_cost <= 300kV": costs[under_300kv_mask].sum(),
            "expanded_cap_length > 300kV": expanded_cap_length[over_300kv_mask].sum(),
            "expanded_cap_length <= 300kV": expanded_cap_length[under_300kv_mask].sum(),
        })
    
    return metrics

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)
    
    all_results = []

    for case_dir in CASE_DIRS:
        case_name = os.path.basename(case_dir)
        networks_dir = os.path.join(case_dir, "networks")
        
        if not os.path.isdir(networks_dir):
            logging.warning(f"Networks directory not found, skipping: {networks_dir}")
            continue
            
        logging.info(f"Processing Case: {case_name}")
        
        for filename, display_name, va in NETWORKS_TO_LOAD:
            filepath = os.path.join(networks_dir, filename)
            
            if not os.path.isfile(filepath):
                logging.warning(f"  - Network file not found, skipping: {filename}")
                continue
            
            logging.info(f"  + Loading and analyzing {display_name}...")
            try:
                n = pypsa.Network(filepath)
                metrics = extract_expansion_metrics(n, va)
                
                res = {
                    "Case": case_name,
                    "Network": display_name,
                    "Voltage Aware": va
                }
                res.update(metrics)
                all_results.append(res)
                
            except Exception as e:
                logging.error(f"  - Failed to process {display_name}: {e}")

    if all_results:
        # Create summary DataFrame
        df = pd.DataFrame(all_results).fillna(0)  # Fill non-applicable splits with 0
        
        # Save to CSV
        output_csv = os.path.join(OUTPUT_BASE_DIR, "expansion_capacity_costs_analysis.csv")
        df.to_csv(output_csv, index=False, float_format='%.2f')
        logging.info(f"Analysis complete. Results saved to {output_csv}")
        
        # Display summary
        print("--- Summary of Grid Expansion Results ---")
        print(df.to_string())
    else:
        logging.warning("No network files were found or processed. No results to show.")
