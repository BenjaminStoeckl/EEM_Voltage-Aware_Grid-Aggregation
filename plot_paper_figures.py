"""
Script to generate paper-quality NPAP-style plots from solved network files.

Usage:
    conda activate pypsa-stable
    python plot_paper_figures.py
"""

import os
import pypsa
from src import plotting

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATA_DIR = os.path.join("data", "networks")
OUTPUT_DIR = os.path.join("data", "paper_figures")

# Network files and their settings: (filename, display_name, voltage_aware)
NETWORKS = [
    ("full_model_grid_exp_solved.nc",       "full_model_grid_exp",     True),
    ("geo_va_aggregation_solved.nc",        "geo_va_aggregation",      True),
    ("geo_non_va_aggregation_solved.nc",    "geo_non_va_aggregation",  False),
    ("elec_va_aggregation_solved.nc",       "elec_va_aggregation",     True),
    ("elec_non_va_aggregation_solved.nc",   "elec_non_va_aggregation", False),
]

# Regions to render (options: 'europe', 'adria', 'sicily')
REGIONS = ["europe", "sicily"]

# Output format: 'pdf', 'png', or 'svg'
FORMAT = "png"

# Display options
SHOW_TITLE = False
SHOW_LEGEND = False

# Investment filter: hide investments below these thresholds (in MVA)
MIN_LINE_INVESTMENT = 50.0   # e.g., 10.0 to hide small line expansions
MIN_TRAFO_INVESTMENT = 50.0  # e.g., 10.0 to hide small trafo expansions

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for nc_file, name, va in NETWORKS:
        path = os.path.join(DATA_DIR, nc_file)
        if not os.path.exists(path):
            print(f"SKIP  {nc_file} (file not found)")
            continue

        print(f"Loading {nc_file} ...")
        n = pypsa.Network(path)
        n.name = name

        print(f"  Plotting ({'voltage-aware' if va else 'voltage-unaware'}) ...")
        plotting.plot_network_paper(
            n,
            output_file=OUTPUT_DIR,
            voltage_aware=va,
            regions=REGIONS,
            fmt=FORMAT,
            show_title=SHOW_TITLE,
            show_legend=SHOW_LEGEND,
            min_line_investment=MIN_LINE_INVESTMENT,
            min_trafo_investment=MIN_TRAFO_INVESTMENT,
        )

    print(f"\nDone. Figures saved to: {os.path.abspath(OUTPUT_DIR)}")
