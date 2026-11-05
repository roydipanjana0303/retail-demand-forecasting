
import pandas as pd
import joblib
from pathlib import Path

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from xgboost import XGBRegressor


# 1. Load training and testing datasets
train_df = pd.read_csv("data/processed/train_data.csv")
test_df = pd.read_csv("data/processed/test_data.csv")

print("Datasets loaded successfully!")


# 2. Select features
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

target = "units_sold"

X_train = train_df[features]
y_train = train_df[target]

X_test = test_df[features]
y_test = test_df[target]


# 3. Create models
models = {
    "Random Forest": RandomForestRegressor(
        n_estimators=100,
        max_depth=15,
        random_state=42,
        n_jobs=-1
    ),

    "XGBoost": XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        random_state=42,
        n_jobs=-1
    )
}


# 4. Train and evaluate models
results = []
prediction_data = test_df[["date", "sku", "units_sold"]].copy()

Path("src/models").mkdir(parents=True, exist_ok=True)

for name, model in models.items():

    print(f"\nTraining {name}...")

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)
    rmse = mean_squared_error(y_test, predictions) ** 0.5
    r2 = r2_score(y_test, predictions)

    results.append({
        "Model": name,
        "MAE": mae,
        "RMSE": rmse,
        "R2 Score": r2
    })

    # Save trained model
    filename = name.lower().replace(" ", "_") + "_model.pkl"

    joblib.dump(
        model,
        f"src/models/{filename}"
    )

    # Save predictions
    prediction_data[f"{name}_prediction"] = predictions

    print(f"{name} training completed!")
    print("MAE:", round(mae, 2))
    print("RMSE:", round(rmse, 2))
    print("R2 Score:", round(r2, 4))


# 5. Compare model performance
comparison = pd.DataFrame(results)

comparison = comparison.sort_values(
    by="MAE",
    ascending=True
)

comparison.to_csv(
    "data/processed/model_comparison.csv",
    index=False
)

print("\nMODEL PERFORMANCE COMPARISON")
print("--------------------------------")
print(comparison.to_string(index=False))


# 6. Identify best model based on MAE
best_model = comparison.iloc[0]["Model"]

print("\nBest model based on MAE:", best_model)


# 7. Save predictions
prediction_data.to_csv(
    "data/processed/model_predictions.csv",
    index=False
)

print("\nAll models and predictions saved successfully!")
