# pattern_recognition.py
# ----------------------
# Computes per-habit streak/behavior patterns for a given user_id (argv[1]).
# Prints a JSON array for Node to read.

import os
import sys
import json
import warnings
from datetime import time

import pandas as pd
from sqlalchemy import create_engine

# --- Silence the specific future warning you saw ---
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message="DataFrameGroupBy.apply operated on the grouping columns",
)

# --- DB connection (use env if available, else your current defaults) ---
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "1234")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "habit_tracker")

engine = create_engine(
    f"mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
)

# --- Optional user_id from argv ---
user_id = sys.argv[1] if len(sys.argv) > 1 else None

# --- Fetch logs joined to habits (to get reminder_time and description) ---
query = """
SELECT
  hl.habit_id,
  hl.log_date,
  hl.status,
  h.reminder_time,
  h.description
FROM habit_logs hl
JOIN habits h ON hl.habit_id = h.habit_id
"""
if user_id:
    query += f" WHERE h.user_id = {int(user_id)}"

df = pd.read_sql(query, engine)

if df.empty:
    print(json.dumps([]))
    sys.exit(0)

# --- Normalize types ---
df["log_date"] = pd.to_datetime(df["log_date"], errors="coerce")

# reminder_time can be TIME / object; normalize to timedelta so we can extract hour easily
# (e.g., '09:00:00' -> Timedelta('0 days 09:00:00'))
df["reminder_time_td"] = pd.to_timedelta(df["reminder_time"].astype(str), errors="coerce")

# Ensure deterministic order
df = df.sort_values(["habit_id", "log_date"]).reset_index(drop=True)

def identify_patterns(group: pd.DataFrame) -> pd.Series:
    # Forward-compatible: drop the grouping column if present
    group = group.copy()
    if "habit_id" in group.columns:
        group = group.drop(columns=["habit_id"])

    # Numeric status for success rate etc.
    group["status_num"] = group["status"].map({"completed": 1, "missed": 0}).fillna(0)

    # Longest continuous completed streak & most-frequent missed streak length
    group["sequence_group"] = (group["status"] != group["status"].shift()).cumsum()
    seq = (
        group.groupby(["sequence_group", "status"], dropna=False)["log_date"]
        .count()
        .reset_index(name="length")
    )

    longest_completed = 0
    if not seq[seq["status"] == "completed"].empty:
        longest_completed = int(seq.loc[seq["status"] == "completed", "length"].max())

    frequent_miss_streak_length = 0
    miss_part = seq[seq["status"] == "missed"]["length"]
    if not miss_part.empty:
        # mode might return multiple values; pick the first
        frequent_miss_streak_length = int(miss_part.mode().iloc[0])

    # Missed days by weekday
    group["weekday"] = group["log_date"].dt.day_name()
    miss_weekdays = (
        group[group["status"] == "missed"]["weekday"].value_counts().to_dict()
    )
    # Convert numpy ints to native int for clean JSON
    miss_weekdays = {k: int(v) for k, v in miss_weekdays.items()}

    # Success rate (%)
    success_rate_percent = round(float(group["status_num"].mean() * 100.0), 2)

    # Success by reminder hour (0-23)
    group["hour"] = group["reminder_time_td"].dt.components["hours"]
    time_success = (group.groupby("hour")["status_num"].mean() * 100).dropna()
    time_success_rates = {int(h): round(float(v), 2) for h, v in time_success.items()}

    # Dates for calendar dots
    completed_dates = (
        group.loc[group["status"] == "completed", "log_date"]
        .dt.strftime("%Y-%m-%d")
        .tolist()
    )
    missed_dates = (
        group.loc[group["status"] == "missed", "log_date"]
        .dt.strftime("%Y-%m-%d")
        .tolist()
    )

    # The habit description is constant within the group; pick the first non-null
    description = group["description"].dropna().iloc[0] if "description" in group.columns and not group["description"].dropna().empty else None

    return pd.Series(
        {
            "description": description,
            "longest_completed_streak": int(longest_completed),
            "frequent_miss_streak_length": int(frequent_miss_streak_length),
            "miss_weekdays": miss_weekdays,
            "success_rate_percent": success_rate_percent,
            "time_success_rates": time_success_rates,
            "completed_dates": completed_dates,
            "missed_dates": missed_dates,
        }
    )

# Group by habit and compute patterns
patterns = (
    df.groupby("habit_id", group_keys=False)
    .apply(identify_patterns, include_groups=False)  # <— prevents the future warning
    .reset_index()  # brings 'habit_id' back as a column
    .rename(columns={"habit_id": "habit_id"})
)

# Convert to JSON (list of dicts)
print(patterns.to_json(orient="records"))
