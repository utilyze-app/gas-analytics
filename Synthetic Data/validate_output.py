import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# Folder containing all your generated files
folder = Path("D:/Utilyze/Synthetic Data/outputs")

# Files to validate + plot
files = [
    "out_summer_p1.csv", "out_summer_p2.csv", "out_summer_p3.csv",
    "out_summer_p4.csv", "out_summer_p5.csv",
    "out_winter_1000.csv", "out_winter_1200.csv", "out_winter_1400.csv", 
    "out_winter_1600.csv", "out_winter_1800.csv", "out_winter_2000.csv",
    "out_winter_2200.csv", "out_winter_2400.csv", "out_winter_2600.csv",
    "out_winter_2800.csv", "out_winter_3000.csv"
]

for file in files:
    path = folder / file
    if not path.exists():
        print(f"❌ Missing file: {file}")
        continue

    df = pd.read_csv(path)
    df["usage_therms"] = df["usage_therms"].astype(float)
    
    # ---- Validation Stats ----
    zero_hours = (df["usage_therms"] == 0).sum()
    total_hours = len(df)
    zero_pct = round(zero_hours / total_hours * 100, 2)
    daily_total = df.groupby("date")["usage_therms"].sum().mean()
    
    print(f"\n✅ {file}")
    print(f"   Rows: {total_hours}")
    print(f"   Avg daily total: {daily_total:.3f} therms/day")
    print(f"   Zero-usage hours: {zero_pct}%")

    # ---- Visualization ----
    # Aggregate by day for smoother visualization
    daily_usage = df.groupby("date")["usage_therms"].sum().reset_index()

    plt.figure(figsize=(10, 4))
    plt.plot(daily_usage["date"], daily_usage["usage_therms"], marker="o", linestyle="-", label="Daily Usage")
    plt.title(f"{file} - Daily Gas Usage")
    plt.xlabel("Date")
    plt.ylabel("Total Therms Used")
    plt.xticks(rotation=45)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.legend()
    plt.show()
