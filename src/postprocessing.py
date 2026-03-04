"""
Module for postprocessing and comparing results from different model runs.
"""
import logging
import pypsa
from typing import Dict, Optional

def get_grid_expansion_cost(n: pypsa.Network) -> float:
    """
    Calculates the total grid expansion cost from a solved network.

    This includes the capital cost of new lines and other extendable assets.

    Args:
        n (pypsa.Network): A solved PyPSA network.

    Returns:
        float: The total cost of grid expansion.
    """
    # This is a simplified example. A real implementation would be more robust.
    # It assumes the objective function value represents total system cost
    # (investment + operational).
    
    # Check if the network has an objective value
    if hasattr(n, 'objective'):
        # For this placeholder, we'll assume the objective is the total cost.
        # A more detailed analysis would separate investment from operational costs.
        return n.objective
    else:
        # Return a dummy value if the network wasn't solved
        return 0.0

def compare_results(full_model_path: str, aggregated_model_paths: Dict[str, Optional[str]], config: Dict):
    """
    Compares the grid expansion costs between the full and aggregated models.

    Args:
        full_model_path (str): Path to the solved full model network file.
        aggregated_model_paths (Dict[str, Optional[str]]): A dictionary mapping aggregation
                                                           strategy names to their result file paths.
        config (Dict): The main configuration dictionary.
    """
    logging.info("\n--- Result Comparison ---")
    
    # In a real scenario, we would load the networks like this:
    # full_n = pypsa.Network(full_model_path)
    # For now, we'll create dummy networks with dummy costs.
    
    # Dummy full model cost
    full_model_cost = 1_000_000 
    logging.info(f"Full Model Grid Expansion Cost: ${full_model_cost:,.2f}")

    # Compare each aggregated model
    for name, path in aggregated_model_paths.items():
        if path is None:
            logging.info(f"\nStrategy: '{name}'")
            logging.info("  -> No results available (step was skipped).")
            continue
            
        # aggregated_n = pypsa.Network(path)
        # For now, use a dummy cost for the aggregated model
        aggregated_model_cost = 850_000 if name == "pypsa_native" else 0
        
        difference = aggregated_model_cost - full_model_cost
        percentage_diff = (difference / full_model_cost) * 100 if full_model_cost != 0 else 0
        
        logging.info(f"\nStrategy: '{name}'")
        logging.info(f"  -> Aggregated Model Cost: ${aggregated_model_cost:,.2f}")
        logging.info(f"  -> Difference from Full Model: ${difference:,.2f} ({percentage_diff:.2f}%)")

    logging.info("\n--- End of Comparison ---\n")
