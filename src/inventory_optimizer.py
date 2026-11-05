
import pandas as pd
import numpy as np
from pathlib import Path


def optimize_inventory(forecast_df, historical_df, lead_time=7):

    recommendations = []

    # Process each product separately
    for sku in forecast_df["sku"].unique():

        # Historical sales for this product
        history = historical_df[
            historical_df["sku"] == sku
        ]["units_sold"]

        # Future predicted demand
        future = forecast_df[
            forecast_df["sku"] == sku
        ]["predicted_demand"]

        # Average daily forecast demand
        avg_daily_demand = future.mean()

        # Demand variability
        demand_std = history.std()

        # Safety stock calculation
        safety_stock = 1.65 * demand_std * np.sqrt(lead_time)

        # Reorder point
        reorder_point = (
            avg_daily_demand * lead_time
        ) + safety_stock

        # Demand during lead time
        lead_time_demand = avg_daily_demand * lead_time

        # Suggested order quantity
        recommended_order = lead_time_demand + safety_stock

        recommendations.append({
            "sku": sku,
            "average_daily_demand": round(avg_daily_demand, 2),
            "lead_time_days": lead_time,
            "safety_stock": round(safety_stock, 2),
            "reorder_point": round(reorder_point, 2),
            "recommended_order_quantity": round(
                recommended_order, 0
            )
        })

    return pd.DataFrame(recommendations)


if __name__ == "__main__":

    # Load datasets
    forecast_df = pd.read_csv(
        "data/processed/forecast_results.csv"
    )

    historical_df = pd.read_csv(
        "data/processed/daily_sales.csv"
    )

    # Set delivery lead time
    LEAD_TIME = 7

    # Generate inventory recommendations
    result = optimize_inventory(
        forecast_df,
        historical_df,
        lead_time=LEAD_TIME
    )

    # Save results
    Path("data/processed").mkdir(
        parents=True,
        exist_ok=True
    )

    result.to_csv(
        "data/processed/inventory_recommendations.csv",
        index=False
    )

    print("\nINVENTORY OPTIMIZATION COMPLETED!")
    print("--------------------------------")

    print("Products analyzed:", len(result))

    print("\nInventory Recommendations:")
    print(result.to_string(index=False))

    print("\nSaved at:")
    print("data/processed/inventory_recommendations.csv")
