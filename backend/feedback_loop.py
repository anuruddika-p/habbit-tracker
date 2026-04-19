import pandas as pd
from sqlalchemy import create_engine, text
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- DB connection ---
try:
    engine = create_engine("mysql+mysqlconnector://root:1234@localhost/habit_tracker")
except Exception as e:
    logging.error(f"Database connection failed: {e}")
    sys.exit(1)

def get_low_feedback():
    """Fetch feedback with rating < 3 that hasn’t been processed yet"""
    query = """
    SELECT rf.feedback_id, rf.rec_id, rf.feedback_rating, rf.feedback_comment,
           r.user_id, r.habit_id, r.message
    FROM recommendation_feedback rf
    JOIN recommendations r ON rf.rec_id = r.rec_id
    WHERE rf.feedback_rating < 3 AND rf.processed = 0
    """
    try:
        df = pd.read_sql(query, engine)
        logging.info(f"Fetched {len(df)} low-feedback entries.")
        return df
    except Exception as e:
        logging.error(f"Error fetching feedback: {e}")
        return pd.DataFrame()

def process_feedback(df: pd.DataFrame):
    if df.empty:
        logging.info("No low feedback to process.")
        return False

    with engine.begin() as con:
        for _, row in df.iterrows():
            rec_id = row["rec_id"]
            feedback_id = row["feedback_id"]

            # Mark the recommendation as inactive
            con.execute(
                text("UPDATE recommendations SET status = 'inactive' WHERE rec_id = :rid"),
                {"rid": rec_id}
            )

            # Mark feedback as processed
            con.execute(
                text("UPDATE recommendation_feedback SET processed = 1 WHERE feedback_id = :fid"),
                {"fid": feedback_id}
            )

            logging.info(f"Marked rec_id={rec_id} inactive (feedback_id={feedback_id}).")

    return True

if __name__ == "__main__":
    feedback_df = get_low_feedback()
    process_feedback(feedback_df)
