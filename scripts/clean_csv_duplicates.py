import pandas as pd

file_path = 'data/historical_data/ES_1min.csv'
print(f"Reading {file_path}...")
df = pd.read_csv(file_path)

print(f"Rows before: {len(df)}")
df.drop_duplicates(subset=['timestamp'], keep='first', inplace=True)
print(f"Rows after: {len(df)}")

df.to_csv(file_path, index=False)
print("Saved cleaned file.")
