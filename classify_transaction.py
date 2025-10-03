import pandas as pd
from data.keyword_map import keyword_map


# Classification function
def classify_transaction(description, keyword_map):
    for keyword, (category, subcategory) in keyword_map.items():
        if keyword.lower() in description.lower():
            # print(f'Match found for description: {description} with keyword: {keyword}')
            return pd.Series([category, subcategory])
    print(f'No match found for description: {description}')
    return pd.Series(["Uncategorized", "Uncategorized"])

# Example usage with a DataFrame
def classify_dataframe(df, keyword_map):
    # Create empty columns first
    df["Category"] = "Uncategorized"
    df["Subcategory"] = "Uncategorized"

    # Apply classification only to rows with a non-null and positive Debit Amount
    mask = df["Debit Amount"].notnull() & (df["Debit Amount"] > 0)
    print(f'Size of Mask: {mask.sum()} not mask: {~mask.sum()}')

    # Apply classification and unpack results correctly
    classified = df.loc[mask, "Transaction Description"].apply(lambda x: classify_transaction(x, keyword_map))
    classified_df = classified.apply(pd.Series)
    df.loc[mask, ["Category", "Subcategory"]] = classified_df.values
    df.loc[~mask, ["Category", "Subcategory"]] = ("Income", "Salary")
    return df


# Example DataFrame
df = pd.read_csv("./data/full_financials.csv")[['Transaction Date', 'Transaction Type', 'Sort Code', 'Account Number','Transaction Description', 'Debit Amount', 'Credit Amount', 'Balance',]]
df = classify_dataframe(df, keyword_map)

#print count NaN values in Category and Subcategory columns
print('Count of NaN in Category:', pd.isna(df['Category']).sum())
print('Count of NaN in Subcategory:', pd.isna(df['Subcategory']).sum())
print(df)

df.to_csv("./data/classified_financials.csv", index=False)