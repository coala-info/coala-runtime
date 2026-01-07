"""
Test script for creating a boxplot using matplotlib.
This script generates sample data and creates a boxplot visualization.
"""

import matplotlib.pyplot as plt
import numpy as np

# Generate sample data
np.random.seed(42)
data = [
    np.random.normal(0, 1, 100),
    np.random.normal(2, 1.5, 100),
    np.random.normal(4, 1, 100),
    np.random.normal(6, 2, 100),
]

# Create boxplot
fig, ax = plt.subplots(figsize=(10, 6))
bp = ax.boxplot(data, labels=["Group A", "Group B", "Group C", "Group D"], patch_artist=True)

# Customize the boxplot
colors = ["lightblue", "lightgreen", "lightcoral", "lightyellow"]
for patch, color in zip(bp["boxes"], colors):
    patch.set_facecolor(color)

ax.set_title("Boxplot Demo - Sample Data Distribution", fontsize=14, fontweight="bold")
ax.set_xlabel("Groups", fontsize=12)
ax.set_ylabel("Values", fontsize=12)
ax.grid(True, alpha=0.3)

# Save the plot
output_path = "/output/boxplot_demo.png"
plt.savefig(output_path, dpi=150, bbox_inches="tight")
print(f"Boxplot saved to: {output_path}")

# Print summary statistics
print("\nSummary Statistics:")
for i, (group_data, label) in enumerate(zip(data, ["Group A", "Group B", "Group C", "Group D"])):
    print(f"{label}: mean={np.mean(group_data):.2f}, std={np.std(group_data):.2f}")

plt.close()
