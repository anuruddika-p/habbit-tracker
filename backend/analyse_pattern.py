import pandas as pd
df = pd.read_csv('C:/Users/gts/habit-tracker/backend/productivity_habit_dataset.csv')
for technique in df['recommended_technique'].unique():
    subset = df[df['recommended_technique'] == technique]
    print(f"{technique}:\n{subset.describe()}\n")
