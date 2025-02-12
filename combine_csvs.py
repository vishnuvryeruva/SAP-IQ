import os
import pandas as pd

# Set the directory containing the CSV files
directory = 'file_vault'

# Maximum file size in bytes (20 MB = 20 * 1024 * 1024)
max_file_size = 5 * 1024 * 1024

# List to store dataframes
df_list = []

# Loop through each file in the directory
for filename in os.listdir(directory):
    if filename.endswith('.csv'):
        file_path = os.path.join(directory, filename)
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size < max_file_size:
            # Read the CSV file if it's less than 20 MB
            df = pd.read_csv(file_path)
            df_list.append(df)
            print(f"File {filename} is {file_size / (1024 * 1024):.2f} MB and has been combined.")
        else:
            print(f"File {filename} is {file_size / (1024 * 1024):.2f} MB and was skipped due to size.")

# Combine all dataframes into one
if df_list:
    combined_df = pd.concat(df_list, ignore_index=True)

    # Save the combined dataframe to a new CSV file
    combined_df.to_csv('combined_output.csv', index=False)

    print("All eligible CSV files have been combined successfully!")
else:
    print("No eligible files to combine.")
