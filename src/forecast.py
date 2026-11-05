
import pandas as pd
import joblib
from pathlib import Path


# 1. Load the best trained model
model = joblib.load("src/models/xgboost_model.pkl")

# 2. Load historical sales
df = pd.read_csv("data/processed/daily_sales.csv")
df["date"] = pd.to_datetime(df["date"])

df = df.sort_values(["sku", "date"])

# 3. Forecast settings
FORECAST_DAYS = 30

features = [
    "day",
    "month",
    "year",
    "day_of_week",
    "is_weekend",
    "lag_1",
    "lag_7",
    "lag_14",
    "rolling_7",
    "rolling_14",
    "rolling_30"
]

all_forecasts = []

# 4. Forecast separately for each product
for sku, group in df.groupby("sku"):

    history = group["units_sold"].astype(float).tolist()

    last_date = group["date"].max()

    print(f"Forecasting product: {sku}")

    for step in range(1, FORECAST_DAYS + 1):

        future_date = last_date + pd.Timedelta(days=step)

        # Date features
        day = future_date.day
        month = future_date.month
        year = future_date.year
        day_of_week = future_date.dayofweek
        is_weekend = int(day_of_week >= 5)

        # Lag features
        lag_1 = history[-1]
        lag_7 = history[-7]
        lag_14 = history[-14]

        # Rolling average features
        rolling_7 = sum(history[-7:]) / 7
        rolling_14 = sum(history[-14:]) / 14
        rolling_30 = sum(history[-30:]) / 30

        # Prepare model input
        input_data = pd.DataFrame([{
            "day": day,
            "month": month,
            "year": year,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "lag_1": lag_1,
            "lag_7": lag_7,
            "lag_14": lag_14,
            "rolling_7": rolling_7,
            "rolling_14": rolling_14,
            "rolling_30": rolling_30
        }])

        # Predict demand
        prediction = float(model.predict(input_data[features])[0])

        # Demand cannot be negative
        prediction = max(0, prediction)

        # Store forecast
        all_forecasts.append({
            "date": future_date,
            "sku": sku,
            "predicted_demand": round(prediction, 2)
        })

        # Add prediction to history for next forecast
        history.append(prediction)


# 5. Create forecast dataframe
forecast_df = pd.DataFrame(all_forecasts)

# 6. Save forecast results
Path("data/processed").mkdir(parents=True, exist_ok=True)

forecast_df.to_csv(
    "data/processed/forecast_results.csv",
    index=False
)

# 7. Display results
print("\nFORECASTING COMPLETED!")
print("--------------------------------")

print("Products forecasted:", forecast_df["sku"].nunique())
print("Forecast days:", FORECAST_DAYS)
print("Total forecast records:", len(forecast_df))

print("\nSample forecasts:")
print(forecast_df.head(10).to_string(index=False))

print("\nForecast saved at:")
print("data/processed/forecast_results.csv")
