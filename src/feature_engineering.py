
import pandas as pd
from pathlib import Path


def create_features(df):

    # 1. Convert date column
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    # 2. Sort by product and date
    df = df.sort_values(["sku", "date"]).copy()

    # 3. Date features
    df["day"] = df["date"].dt.day
    df["month"] = df["date"].dt.month
    df["year"] = df["date"].dt.year
    df["day_of_week"] = df["date"].dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    # 4. Lag features
    df["lag_1"] = df.groupby("sku")["units_sold"].shift(1)
    df["lag_7"] = df.groupby("sku")["units_sold"].shift(7)
    df["lag_14"] = df.groupby("sku")["units_sold"].shift(14)

    # 5. Rolling average features
    df["rolling_7"] = df.groupby("sku")["units_sold"].transform(
        lambda x: x.shift(1).rolling(7).mean()
    )

    df["rolling_14"] = df.groupby("sku")["units_sold"].transform(
        lambda x: x.shift(1).rolling(14).mean()
    )

    df["rolling_30"] = df.groupby("sku")["units_sold"].transform(
        lambda x: x.shift(1).rolling(30).mean()
    )

    return df


if __name__ == "__main__":

    # Load daily sales dataset
    input_path = Path("data/processed/daily_sales.csv")
    output_path = Path("data/processed/featured_sales.csv")

    print("Loading sales dataset...")

    df = pd.read_csv(input_path)

    # Create ML features
    result = create_features(df)

    # Save feature-engineered dataset
    result.to_csv(output_path, index=False)

    print("\nFeature Engineering Completed!")
    print("--------------------------------")
    print("Original dataset shape:", df.shape)
    print("Featured dataset shape:", result.shape)

    print("\nCreated Features:")
    print([
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
    ])

    print("\nMissing values in new features:")
    print(result.isnull().sum())

    print("\nSample data:")
    print(
        result[
            [
                "date",
                "sku",
                "units_sold",
                "lag_1",
                "lag_7",
                "lag_14",
                "rolling_7",
                "rolling_14",
                "rolling_30"
            ]
        ].tail(10).to_string(index=False)
    )

    print("\nFeature-engineered dataset saved at:")
    print(output_path)
