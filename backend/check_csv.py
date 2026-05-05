"""
Run this from the backend folder:
python check_csv.py

It will show you exactly what column names are in your CSV files.
"""
import csv
import os

data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
data_dir = os.path.abspath(data_dir)

print(f"\nLooking in: {data_dir}\n")

for filename in ['mubawab_data.csv', 'tayara_data.csv']:
    filepath = os.path.join(data_dir, filename)
    if not os.path.exists(filepath):
        print(f"❌ NOT FOUND: {filename}")
        continue

    with open(filepath, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        print(f"✅ {filename}")
        print(f"   Columns: {columns}")

        # Show first 2 rows
        for i, row in enumerate(reader):
            if i >= 2:
                break
            print(f"   Row {i+1}: {dict(row)}")
        print()
