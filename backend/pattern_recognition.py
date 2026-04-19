# pattern_recognition.py
# ----------------------
# Computes per-habit streak/behavior patterns for a given user_id (argv[1]).
# Prints a JSON array for Node to read.

import os
import sys
import json
import warnings
import pandas as pd
from sqlalchemy import create_engine

# --- Silence future warning (pandas groupby apply) ---
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message="DataFrameGroupBy.apply operated on the grouping columns",
)

# --- DB connection (env or fallback) ---
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "1234")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "habit_tracker")

engine = create_engine(
    f"mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
)

# --- Optional user_id from argv ---
user_id = sys.argv[1] if len(sys.argv) > 1 else None

# --- Fetch logs joined to habits and latest active recommendation ---
query = """
SELECT
  hl.habit_id,
  hl.log_date,
  hl.status,
  h.reminder_time,
  h.description,
  (SELECT r.rec_id FROM recommendations r 
   WHERE r.habit_id = h.habit_id AND r.status = 'active' 
   ORDER BY r.generated_on DESC LIMIT 1) as active_rec_id
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
df["reminder_time_td"] = pd.to_timedelta(df["reminder_time"].astype(str), errors="coerce")
df = df.sort_values(["habit_id", "log_date"]).reset_index(drop=True)

# --- Pattern extraction per habit ---
def identify_patterns(group: pd.DataFrame) -> pd.Series:
    g = group.copy()

    # Encode status numeric (completed=1, missed=0)
    g["status_num"] = g["status"].map({"completed": 1, "missed": 0}).fillna(0)

    # Sequence groups for streak detection
    g["sequence_group"] = (g["status"] != g["status"].shift()).cumsum()
    seq = (
        g.groupby(["sequence_group", "status"], dropna=False)["log_date"]
        .count()
        .reset_index(name="length")
    )

    # Longest completed streak
    longest_completed = 0
    if not seq[seq["status"] == "completed"].empty:
        longest_completed = int(seq.loc[seq["status"] == "completed", "length"].max())

    # Most common missed streak length
    frequent_miss_streak_length = 0
    miss_part = seq[seq["status"] == "missed"]["length"]
    if not miss_part.empty:
        frequent_miss_streak_length = int(miss_part.mode().iloc[0])

    # Current miss streak (trailing consecutive misses)
    current_miss_streak = 0
    if not g.empty:
        last_status = g.iloc[-1]["status"]
        if last_status == "missed":
            last_seq_group = g.iloc[-1]["sequence_group"]
            current_seq_row = seq[seq["sequence_group"] == last_seq_group]
            if not current_seq_row.empty:
                current_miss_streak = int(current_seq_row["length"].iloc[0])

    # Detect if habit needs a new strategy (current miss streak >= 3)
    needs_new_strategy = current_miss_streak >= 3

    # Missed weekdays
    g["weekday"] = g["log_date"].dt.day_name()
    miss_weekdays = {
        k: int(v)
        for k, v in g[g["status"] == "missed"]["weekday"].value_counts().to_dict().items()
    }

    # Success rate (%)
    success_rate_percent = round(float(g["status_num"].mean() * 100.0), 2)

    # Success by reminder hour
    g["hour"] = g["reminder_time_td"].dt.components["hours"]
    time_success = (g.groupby("hour")["status_num"].mean() * 100).dropna()
    time_success_rates = {int(h): round(float(v), 2) for h, v in time_success.items()}

    # Dates
    completed_dates = g.loc[g["status"] == "completed", "log_date"].dt.strftime("%Y-%m-%d").tolist()
    missed_dates = g.loc[g["status"] == "missed", "log_date"].dt.strftime("%Y-%m-%d").tolist()

    # Active rec_id (first non-null in group)
    active_rec_id = g["active_rec_id"].dropna().iloc[0] if "active_rec_id" in g.columns and not g["active_rec_id"].dropna().empty else None

    # Description: pick first non-null
    description = (
        g["description"].dropna().iloc[0]
        if "description" in g.columns and not g["description"].dropna().empty
        else None
    )

    return pd.Series(
        {
            "habit_id": int(g["habit_id"].iloc[0]) if not g.empty else None,
            "description": description,
            "rec_id": active_rec_id,
            "longest_completed_streak": int(longest_completed),
            "frequent_miss_streak_length": int(frequent_miss_streak_length),
            "current_miss_streak": current_miss_streak,
            "miss_weekdays": miss_weekdays,
            "success_rate_percent": success_rate_percent,
            "time_success_rates": time_success_rates,
            "completed_dates": completed_dates,
            "missed_dates": missed_dates,
            "needs_new_strategy": needs_new_strategy,
        }
    )

# --- Apply per habit ---
patterns = (
    df.groupby("habit_id", group_keys=False)
    .apply(identify_patterns, include_groups=True)  # ← Fixed: Include grouping column
    .reset_index(drop=True)
)

# --- Output JSON ---
print(patterns.to_json(orient="records"))