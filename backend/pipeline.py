
from pathlib import Path
import re

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
RESULT_DIR = BASE_DIR / "data" / "upload_results"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

FEATURES = [
    "day", "month", "year", "day_of_week", "is_weekend",
    "lag_1", "lag_7", "lag_14",
    "rolling_7", "rolling_14", "rolling_30"
]


def normalize_name(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def detect_column(columns, candidates):
    lookup = {normalize_name(col): col for col in columns}

    for candidate in candidates:
        key = normalize_name(candidate)
        if key in lookup:
            return lookup[key]

    return None


def analyze_dataset(file_path):
    path = Path(file_path)

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    elif path.suffix.lower() == ".xlsx":
        df = pd.read_excel(path)
    else:
        raise ValueError("Only CSV and XLSX files are supported.")

    if df.empty:
        raise ValueError("The uploaded dataset is empty.")

    if len(df.columns) < 2:
        raise ValueError("The dataset must contain at least two columns.")

    # General dataset profiling
    profile = {
        "filename": path.name,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "column_names": df.columns.astype(str).tolist(),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "numeric_columns": df.select_dtypes(include="number").columns.tolist(),
        "categorical_columns": df.select_dtypes(
            include=["object", "category"]
        ).columns.tolist()
    }

    # Detect retail forecasting columns
    date_col = detect_column(
        df.columns,
        ["date", "order_date", "sales_date", "transaction_date", "timestamp"]
    )

    product_col = detect_column(
        df.columns,
        ["sku", "product_id", "product", "item_id", "product_code", "item"]
    )

    sales_col = detect_column(
        df.columns,
        ["units_sold", "sales", "quantity_sold", "demand",
         "units", "quantity", "qty", "sold_quantity"]
    )

    profile["retail_columns_detected"] = {
        "date": str(date_col) if date_col is not None else None,
        "product": str(product_col) if product_col is not None else None,
        "sales": str(sales_col) if sales_col is not None else None
    }

    if not all([date_col, product_col, sales_col]):
        profile["analysis_type"] = "general"
        profile["message"] = (
            "Dataset profiling completed. Retail forecasting requires "
            "a date, product and sales quantity column."
        )
        profile["numeric_summary"] = (
            df.select_dtypes(include="number")
            .describe()
            .replace({np.nan: None})
            .to_dict()
        )
        return profile

    # Prepare retail dataset
    retail = df[[date_col, product_col, sales_col]].copy()

    retail.columns = ["date", "sku", "units_sold"]

    retail["date"] = pd.to_datetime(retail["date"], errors="coerce")
    retail["units_sold"] = pd.to_numeric(
        retail["units_sold"], errors="coerce"
    )

    retail = retail.dropna(
        subset=["date", "sku", "units_sold"]
    )

    retail["sku"] = retail["sku"].astype(str).str.strip()
    retail = retail[retail["sku"] != ""]

    # Exclude negative quantities from demand forecasting
    retail = retail[retail["units_sold"] >= 0]

    if retail.empty:
        raise ValueError("No valid non-negative retail sales records found.")

    daily = (
        retail.groupby(["date", "sku"], as_index=False)["units_sold"]
        .sum()
        .sort_values(["sku", "date"])
    )

    profile["analysis_type"] = "retail"
    profile["valid_sales_rows"] = int(len(retail))
    profile["products"] = int(daily["sku"].nunique())
    profile["total_units_sold"] = round(float(daily["units_sold"].sum()), 2)
    profile["average_units_per_product_day"] = round(
        float(daily["units_sold"].mean()), 2
    )
    profile["date_from"] = str(daily["date"].min().date())
    profile["date_to"] = str(daily["date"].max().date())

    # Build lag and rolling features
    daily["day"] = daily["date"].dt.day
    daily["month"] = daily["date"].dt.month
    daily["year"] = daily["date"].dt.year
    daily["day_of_week"] = daily["date"].dt.dayofweek
    daily["is_weekend"] = (daily["day_of_week"] >= 5).astype(int)

    grouped = daily.groupby("sku")["units_sold"]

    daily["lag_1"] = grouped.shift(1)
    daily["lag_7"] = grouped.shift(7)
    daily["lag_14"] = grouped.shift(14)

    daily["rolling_7"] = grouped.transform(
        lambda x: x.shift(1).rolling(7).mean()
    )
    daily["rolling_14"] = grouped.transform(
        lambda x: x.shift(1).rolling(14).mean()
    )
    daily["rolling_30"] = grouped.transform(
        lambda x: x.shift(1).rolling(30).mean()
    )

    featured = daily.dropna(subset=FEATURES + ["units_sold"]).copy()

    if featured.empty or len(featured) < 30:
        profile["forecast_available"] = False
        profile["message"] = (
            "Retail data detected, but there is not enough history "
            "to train a reliable forecasting model. More historical "
            "records are needed."
        )
        return profile

    # Use the latest 20% of dates for testing
    dates = sorted(featured["date"].unique())
    split_index = max(1, int(len(dates) * 0.8))

    if split_index >= len(dates):
        split_index = len(dates) - 1

    split_date = dates[split_index]

    train = featured[featured["date"] < split_date]
    test = featured[featured["date"] >= split_date]

    if len(train) < 20 or len(test) < 1:
        profile["forecast_available"] = False
        profile["message"] = "Not enough training or testing records."
        return profile

    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=12,
        random_state=42,
        n_jobs=-1
    )

    model.fit(train[FEATURES], train["units_sold"])

    predictions = np.maximum(0, model.predict(test[FEATURES]))

    mae = mean_absolute_error(test["units_sold"], predictions)
    rmse = mean_squared_error(test["units_sold"], predictions) ** 0.5
    r2 = (
        r2_score(test["units_sold"], predictions)
        if len(test) >= 2 else None
    )

    profile["model_performance"] = {
        "model": "Random Forest",
        "mae": round(float(mae), 3),
        "rmse": round(float(rmse), 3),
        "r2_score": round(float(r2), 4) if r2 is not None else None
    }

    # Forecast next 30 days using each product's history
    forecast_records = []
    last_date = daily["date"].max()

    for sku in daily["sku"].unique():
        history = (
            daily[daily["sku"] == sku]
            .sort_values("date")["units_sold"]
            .astype(float)
            .tolist()
        )

        if len(history) < 30:
            continue

        for day_offset in range(1, 31):
            future_date = last_date + pd.Timedelta(days=day_offset)

            row = pd.DataFrame([{
                "day": future_date.day,
                "month": future_date.month,
                "year": future_date.year,
                "day_of_week": future_date.dayofweek,
                "is_weekend": int(future_date.dayofweek >= 5),
                "lag_1": history[-1],
                "lag_7": history[-7],
                "lag_14": history[-14],
                "rolling_7": float(np.mean(history[-7:])),
                "rolling_14": float(np.mean(history[-14:])),
                "rolling_30": float(np.mean(history[-30:]))
            }])

            predicted = max(0, float(model.predict(row[FEATURES])[0]))
            history.append(predicted)

            forecast_records.append({
                "date": future_date.strftime("%Y-%m-%d"),
                "sku": sku,
                "predicted_demand": round(predicted, 2)
            })

    if not forecast_records:
        profile["forecast_available"] = False
        profile["message"] = (
            "The dataset is retail-compatible, but no product has "
            "30 days of history for forecasting."
        )
        return profile

    forecast_df = pd.DataFrame(forecast_records)

    # Inventory estimates; actual on-hand stock is not supplied
    inventory_records = []

    for sku in forecast_df["sku"].unique():
        future = forecast_df.loc[
            forecast_df["sku"] == sku, "predicted_demand"
        ]

        past = daily.loc[
            daily["sku"] == sku, "units_sold"
        ]

        avg_demand = float(future.mean())
        demand_std = float(past.std()) if len(past) > 1 else 0.0

        lead_time = 7
        safety_stock = 1.65 * demand_std * np.sqrt(lead_time)
        lead_time_demand = avg_demand * 7

        inventory_records.append({
            "sku": sku,
            "average_daily_demand": round(avg_demand, 2),
            "lead_time_days": lead_time,
            "safety_stock": round(safety_stock, 2),
            "reorder_point": round(lead_time_demand + safety_stock, 2),
            "recommended_order_quantity": int(
                np.ceil(lead_time_demand + safety_stock)
            )
        })

    # Add readable product names using actual dataset metadata
    inventory_df = pd.DataFrame(inventory_records)

    metadata_columns = {
        "brand": detect_column(df.columns, ["brand", "brand_name"]),
        "category": detect_column(df.columns, ["category", "product_category"]),
        "segment": detect_column(df.columns, ["segment", "product_segment"])
    }

    metadata_fields = {
        name: column
        for name, column in metadata_columns.items()
        if column is not None
    }

    if metadata_fields:
        metadata_df = df[
            [product_col] + list(metadata_fields.values())
        ].copy()

        metadata_df = metadata_df.rename(
            columns={
                product_col: "sku",
                **{
                    column: name
                    for name, column in metadata_fields.items()
                }
            }
        )

        metadata_df["sku"] = metadata_df["sku"].astype(str).str.strip()

        # Keep metadata only when it is consistent for that SKU
        for name in metadata_fields:
            metadata_df[name] = (
                metadata_df[name].fillna("").astype(str).str.strip()
            )

            counts = metadata_df.groupby("sku")[name].nunique()
            valid_skus = counts[counts == 1].index
            values = metadata_df.groupby("sku")[name].first()

            inventory_df[name] = inventory_df["sku"].map(values)

            inventory_df.loc[
                ~inventory_df["sku"].isin(valid_skus), name
            ] = ""

            inventory_df[name] = inventory_df[name].fillna("")

    # Create a human-readable product name
    for column in ["brand", "category", "segment"]:
        if column not in inventory_df.columns:
            inventory_df[column] = ""

    inventory_df["product_name"] = (
        inventory_df["brand"].fillna("").astype(str).str.strip()
        + " "
        + inventory_df["category"].fillna("").astype(str).str.strip()
        + " - "
        + inventory_df["segment"].fillna("").astype(str).str.strip()
    ).str.strip(" -")

    # Fallback only if the dataset does not contain usable product metadata
    missing_names = (
        inventory_df["product_name"].isna()
        | inventory_df["product_name"].eq("")
    )

    inventory_df.loc[missing_names, "product_name"] = (
        "Product " + inventory_df.loc[missing_names, "sku"].astype(str)
    )

    # Save results under a separate directory for each upload
    result_dir = RESULT_DIR / path.stem
    result_dir.mkdir(parents=True, exist_ok=True)

    daily.to_csv(result_dir / "daily_sales.csv", index=False)
    forecast_df.to_csv(result_dir / "forecast_results.csv", index=False)

    inventory_df.to_csv(
        result_dir / "inventory_recommendations.csv", index=False
    )

    pd.DataFrame([profile["model_performance"]]).to_csv(
        result_dir / "model_comparison.csv", index=False
    )

    profile["forecast_available"] = True
    profile["forecast_days"] = int(forecast_df["date"].nunique())
    profile["forecast_records"] = int(len(forecast_df))
    profile["forecast_total_demand"] = round(
        float(forecast_df["predicted_demand"].sum()), 2
    )
    profile["result_directory"] = str(result_dir.relative_to(BASE_DIR))
    profile["message"] = (
        "Dataset analyzed and a new forecasting model trained successfully."
    )

    return profile
