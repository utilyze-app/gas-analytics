import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# Folder containing all your generated files
base_path = Path("D:/Utilyze/Synthetic Data/outputs")

# Files to compare
datasets = {
    "Aug - 1 Person (Summer)": base_path / "out_summer_p1.csv",
    "Aug - 3 People (Baseline)": base_path / "out_summer_p3.csv",
    "Jan - 1000 sqft (Winter)": base_path / "out_winter_1000.csv",
    "Jan - 1400 sqft (Winter)": base_path / "out_winter_1400.csv"
}

plt.figure(figsize=(10, 6))
colors = ['#2E86C1', '#5DADE2', '#E67E22', '#DC7633']

for i, (title, file) in enumerate(datasets.items(), 1):
    df = pd.read_csv(file)
    df["hour"] = pd.to_datetime(df["time"], format="%H:%M:%S").dt.hour
    hourly_avg = df.groupby("hour")["usage_therms"].mean()
    
    plt.subplot(2, 2, i)
    plt.bar(hourly_avg.index, hourly_avg.values, color=colors[i-1])
    plt.title(f"{title} - Hourly Average Usage Pattern")
    plt.xlabel("Hour of Day")
    plt.ylabel("Avg Usage (therms)")
    plt.grid(axis="y", linestyle="--", alpha=0.6)

plt.tight_layout()
plt.show()
