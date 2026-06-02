import csv
import os
from collections import defaultdict
from statistics import median, mean
from lib import parse_filename

# Mode: "print" (current console output) or "csv" (export summary CSV)
MODE = "csv"
# When MODE == "csv", write just: recipe_name, mean, median
OUTPUT_CSV_PATH = r"Z:\Shared\Muse\job_times_summary.csv"
# Path to the CSV file
CSV_PATH = r"Z:\Shared\Muse\log.csv"
# Path to the folder containing Fixed files for recipe lookup
FIXED_FOLDER = r"Z:\Shared\Muse\Fixed"

def normalize_recipe_name(recipe_name):
    """Normalize recipe name based on consolidation rules."""
    recipe_lower = recipe_name.lower()
    
    # Anything containing "Ornament" is all the same recipe
    if "ornament" in recipe_lower:
        return "Ornament"
    
    # Check for "rocksbottom" first (before general "rocks") to ensure it gets its own category
    if "rocksbottom" in recipe_lower:
        return "Bottom Rocks"
    
    # Anything containing "posh" is counted as Rocks
    if "posh" in recipe_lower:
        return "Rocks"
    
    # Anything containing "rocks" is all the same recipe
    if "rocks" in recipe_lower:
        return "Rocks"
    
    # All other recipes stay as-is
    return recipe_name

# First, build barcode-to-recipe map from all files in Fixed folder
barcode_to_recipe = {}
for filename in os.listdir(FIXED_FOLDER):
    if filename.endswith(".png"):
        barcode, recipe_name, quantity = parse_filename(filename)
        if barcode and recipe_name:
            barcode_to_recipe[barcode] = recipe_name

total_times = []
recipe_times = defaultdict(list)

with open(CSV_PATH, newline='') as f:
    reader = csv.reader(f)
    for row in reader:
        if not row or len(row) < 2:
            continue
        barcode = str(row[0]).strip()
        if barcode.lower() == "barcode":
            continue
        try:
            time_val = int(row[1])
        except ValueError:
            continue
        # Always add to total times for overall stats
        total_times.append(time_val)
        
        # Only add to recipe times if barcode has a matching file in Fixed folder
        recipe = barcode_to_recipe.get(barcode)
        if recipe:
            normalized_recipe = normalize_recipe_name(recipe)
            recipe_times[normalized_recipe].append(time_val)

def safe_mean(lst):
    return mean(lst) if lst else 0

def safe_median(lst):
    return median(lst) if lst else 0

print(f"Total jobs: {len(total_times)}")
print(f"Overall average (mean) time: {safe_mean(total_times):.2f} seconds")
print(f"Overall median time: {safe_median(total_times):.2f} seconds\n")

rows = [
    (recipe, safe_mean(times), safe_median(times), len(times))
    for recipe, times in sorted(recipe_times.items())
]

if MODE.lower() == "csv":
    with open(OUTPUT_CSV_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["recipe_name", "mean", "median", "sample_size"])
        for recipe, mean_val, median_val, count in rows:
            writer.writerow([recipe, f"{mean_val:.2f}", f"{median_val:.2f}", count])
    print(f"Wrote summary CSV to: {OUTPUT_CSV_PATH}")
else:
    print("Average time per recipe (mean + median):")
    for recipe, mean_val, median_val, count in rows:
        print(f"  {recipe:20}: mean={mean_val:6.2f} s, median={median_val:6.2f} s ({count} jobs)")

        # Show top 5 longest jobs for this recipe
        top_5 = sorted(recipe_times[recipe], reverse=True)[:5]
        if top_5:
            print(f"    Top 5 longest jobs: {', '.join(f'{t:.2f}s' for t in top_5)}")
        print()