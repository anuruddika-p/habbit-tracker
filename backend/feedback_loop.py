import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.sql import text
import logging
import random
import re
import sys
import os
import numpy as np
from datetime import datetime, timedelta, date

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Database connection
try:
    engine = create_engine('mysql+mysqlconnector://root:1234@localhost/habit_tracker')
except Exception as e:
    logging.error(f"Database connection failed: {e}")
    sys.exit(1)

def _scale(x, a, b, lo, hi):
    if x is None or np.isnan(x): return int((lo+hi)/2)
    x = max(a, min(b, x))
    r = (x-a)/(b-a) if b != a else 0.5
    return int(round(lo + r*(hi-lo)))

def compute_real_stats(user_id, habit_id, window_days=30):
    start_date = (date.today() - timedelta(days=window_days)).isoformat()
    with engine.connect() as con:
        rows = con.execute(
            text("""
                SELECT hl.status, hl.feedback_rating, hl.log_date, h.frequency, h.reminder_time
                FROM habit_logs hl
                JOIN habits h ON hl.habit_id = h.habit_id
                WHERE h.user_id = :uid
                  AND hl.habit_id = :hid
                  AND hl.log_date >= :start_date
                ORDER BY hl.log_date
            """),
            {"uid": user_id, "hid": habit_id, "start_date": start_date}
        ).mappings().all()

    if not rows:
        return None  # fall back to safe defaults in map_to_dataset

    df = pd.DataFrame(rows)
    df["is_missed"] = (df["status"] == "missed").astype(int)
    df["is_completed"] = (df["status"] == "completed").astype(int)

    if "reminder_time" in df:
        # convert to hour safely
        hours = pd.to_timedelta(df["reminder_time"].astype(str), errors="coerce").dt.components["hours"]
        df["hour"] = hours
        hour_success = df.groupby("hour")["is_completed"].mean().dropna()
        best_hour = int(hour_success.idxmax()) if not hour_success.empty else None
    else:
        best_hour = None

    # most missed weekday
    df["weekday"] = pd.to_datetime(df["log_date"]).dt.day_name()
    miss_counts = df.loc[df["is_missed"] == 1, "weekday"].value_counts()
    most_missed_weekday = miss_counts.index[0] if not miss_counts.empty else None

    miss_ratio = float(df["is_missed"].mean())           # 0..1
    success_ratio = float(df["is_completed"].mean())     # 0..1
    avg_rating = float(df["feedback_rating"].dropna().mean()) if "feedback_rating" in df else None

    # streak proxy: longest consecutive completed (approx)
    df = df.sort_values("log_date")
    grp = (df["status"] != df["status"].shift()).cumsum()
    streaks = df.groupby([grp, "status"]).size().reset_index(name="len")
    longest_completed = int(streaks.loc[streaks["status"]=="completed", "len"].max()) if (streaks["status"]=="completed").any() else 0

    # Map to your model feature scales
    procrastination_level = _scale(miss_ratio, 0, 1, 1, 10)
    motivation_level      = _scale(avg_rating if avg_rating is not None else (1-success_ratio)*5, 0, 5, 1, 10)
    fatigue_level         = _scale(5 - (avg_rating or 3), 0, 5, 1, 10)      # crude proxy
    task_complexity       = _scale(1-success_ratio, 0, 1, 1, 10)           # harder → more misses
    focus_span            = _scale(longest_completed, 0, 10, 20, 60)
    time_availability     = _scale(success_ratio, 0, 1, 60, 240)

    return dict(
        procrastination_level=procrastination_level,
        motivation_level=motivation_level,
        fatigue_level=fatigue_level,
        task_complexity=task_complexity,
        focus_span=focus_span,
        time_availability=time_availability,
        best_hour=best_hour,
        most_missed_weekday=most_missed_weekday,
    )

DATASET_PATH = 'C:/Users/gts/habit-tracker/backend/productivity_habit_dataset.csv'

if not os.path.exists(DATASET_PATH):
    logging.error(f"CSV file not found: {DATASET_PATH}")
    sys.exit(1)
if not os.access(DATASET_PATH, os.R_OK | os.W_OK):
    logging.error(f"No read/write permission for CSV: {DATASET_PATH}")
    sys.exit(1)

ALTERNATIVE_MAP = {
    '2 Minute Rule': 'Pomodoro',
    '90/90/1 Rule': 'Eisenhower Matrix',
    'Pomodoro': 'Time Blocking',
    '5 AM Club': 'Habit Stacking',
    'Eisenhower Matrix': '2 Minute Rule',
    'Habit Stacking': 'Reward and Reinforcement',
    'Reward and Reinforcement': '5 AM Club'
}
ALL_TECHNIQUES = list(ALTERNATIVE_MAP.keys())

def get_low_feedback():
    query = """
    SELECT rf.*, r.message, r.user_id, r.habit_id, u.dob, u.gender, h.frequency, h.time_preference
    FROM recommendation_feedback rf
    JOIN recommendations r ON rf.rec_id = r.rec_id
    JOIN user u ON r.user_id = u.user_id
    LEFT JOIN habits h ON r.habit_id = h.habit_id
    WHERE rf.feedback_rating < 3 AND rf.processed = 0
    """
    try:
        df = pd.read_sql(query, engine)
        df['recommended_technique'] = df['message'].apply(lambda m: re.search(r'Recommended technique: (.*)', m).group(1) if re.search(r'Recommended technique: (.*)', m) else 'Unknown')
        logging.info(f"Fetched {len(df)} low-feedback entries.")
        return df
    except Exception as e:
        logging.error(f"Error fetching feedback: {e}")
        return pd.DataFrame()

def get_habit_count(user_id):
    with engine.connect() as con:
        row = con.execute(
            text("SELECT COUNT(*) AS c FROM habits WHERE user_id = :uid"),
            {"uid": user_id}
        ).mappings().first()
    return int(row["c"] or 0)

def map_to_dataset(row):
    try:
        age = (pd.to_datetime('today') - pd.to_datetime(row['dob'])).days // 365 if 'dob' in row and pd.notnull(row['dob']) else 30
    except:
        age = 30
    user_id = row.get("user_id")
    habit_id = row.get("habit_id")

    # real stats from logs (fallback if none)
    stats = compute_real_stats(user_id, habit_id) if (user_id and habit_id) else None
    procrastination_level = stats["procrastination_level"] if stats else 5
    motivation_level      = stats["motivation_level"] if stats else 5
    fatigue_level         = stats["fatigue_level"] if stats else 5
    task_complexity       = stats["task_complexity"] if stats else 5
    focus_span            = stats["focus_span"] if stats else 40
    time_availability     = stats["time_availability"] if stats else 120
    
    current_habits_count = get_habit_count(user_id) if user_id else 1
    goal_clarity = 6           # neutral default (stop randomizing)
    sleep_hours = 7            # neutral default unless you track it
    morning_person = '1' if row.get('time_preference') == 'Morning' else '0'

    failed_tech = row.get('recommended_technique', 'Unknown')
    alternative = ALTERNATIVE_MAP.get(failed_tech, random.choice(ALL_TECHNIQUES))
    
    return {
        'age': age,
        'gender': row.get('gender', 'Other'),
        'procrastination_level': procrastination_level,
        'motivation_level': motivation_level,
        'fatigue_level': fatigue_level,
        'sleep_hours': sleep_hours,
        'task_complexity': task_complexity,
        'current_habits_count': current_habits_count,
        'morning_person': morning_person,
        'goal_clarity': goal_clarity,
        'focus_span': focus_span,
        'time_availability': time_availability,
        'recommended_technique': alternative
    }

def update_dataset(feedback_df):
    if feedback_df.empty:
        logging.info("No feedback to process.")
        return False
    
    new_rows = [map_to_dataset(row) for _, row in feedback_df.iterrows()]
    new_df = pd.DataFrame(new_rows)
    
    try:
        existing_df = pd.read_csv(DATASET_PATH)
        updated_df = pd.concat([existing_df, new_df], ignore_index=True)
        updated_df.to_csv(DATASET_PATH, index=False)
        logging.info(f"Appended {len(new_df)} new rows to dataset.")
        
        feedback_ids = feedback_df['feedback_id'].tolist()
        if feedback_ids:
            stmt = text("""
                UPDATE recommendation_feedback
                SET processed = 1
                WHERE feedback_id IN :ids
            """).bindparams(bindparam("ids", expanding=True))
            with engine.begin() as con:
                con.execute(stmt, {"ids": feedback_ids})
        
        return True
    except Exception as e:
        logging.error(f"Error updating dataset: {e}")
        return False

if __name__ == "__main__":
    feedback_df = get_low_feedback()
    update_dataset(feedback_df)  # No retraining needed