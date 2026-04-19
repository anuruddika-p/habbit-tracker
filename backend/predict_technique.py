# predict_technique.py (with habit keyword mapping)
import sys
import json
import logging
from typing import Dict, List, Tuple, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="C:/Users/gts/habit-tracker/backend/predict_technique.log",
)

# -----------------------------------------------------------
# Keyword categories for habit detection
# -----------------------------------------------------------
HABIT_KEYWORDS = {
    "sleep": ["sleep", "bedtime", "nap", "rest", "wake up", "go to bed"],
    "exercise": ["exercise", "workout", "run", "yoga", "gym", "fitness"],
    "study": ["study", "learn", "read", "course", "class", "revision"],
    "productivity": ["write", "project", "code", "task", "work", "email"],
    "nutrition": ["diet", "eat", "water", "meal", "drink", "breakfast"],
    "mindfulness": ["meditate", "mindfulness", "breathe", "journal", "gratitude"],
}

# -----------------------------------------------------------
# Recommendation Techniques
# -----------------------------------------------------------
T = {
    "EISENHOWER": "Eisenhower Matrix",
    "TWO_MIN": "2 Minute Rule",
    "CLUB_5AM": "5 AM Club",
    "RULE_90901": "90/90/1 Rule",
    "POMODORO": "Pomodoro",
    "REWARD": "Reward and Reinforcement",
    "STACK": "Habit Stacking",
    "TIME_BLOCK": "Time Blocking",
    "SPACED": "Spaced Repetition",
    "INTENT": "Implementation Intentions",
    "ENVIRONMENT": "Environment Design",
}

# -----------------------------------------------------------
# Rule explanations
# -----------------------------------------------------------
RULE_TEXT = {
    "R1": "High procrastination / complex tasks → Eisenhower Matrix.",
    "R2": "Very low time or high procrastination → 2 Minute Rule.",
    "R3": "Morning person + motivation → leverage early deep work (5 AM Club).",
    "R4": "Clear goals and ≥90 min → 90/90/1 deep focus.",
    "R5": "Short focus span → Pomodoro boosts focus.",
    "R6": "Low motivation / high fatigue → Reward & Reinforcement.",
    "R7": "Managing many habits → Habit Stacking reduces friction.",
    "R8": "Low sleep/energy → Time Blocking protects energy.",
    "R9": "High cognitive load → Time Blocking reduces switching.",
    "R10": "Best focus hours not morning → Time Blocking at peak hours.",
    "R11": "High motivation + medium time → Pomodoro sprints.",
    "R12": "Default gentle start: 2 Minute Rule.",
    "HX1": "Exercise habits → start tiny (2 Minute Rule).",
    "HX2": "Exercise habits → rewards increase consistency.",
    "HS1": "Study habits → Pomodoro prevents burnout.",
    "HS2": "Study habits → Spaced Repetition improves memory.",
    "HN1": "Nutrition habits → Implementation Intentions help consistency.",
    "HN2": "Nutrition habits → Environment design reduces friction.",
    "HM1": "Mindfulness habits → Stack onto existing cues.",
    "HM2": "Mindfulness habits → Block time to avoid skipping.",
    "HL1": "Sleep habits → Time Blocking builds consistent routine.",
}

# -----------------------------------------------------------
# Input helpers
# -----------------------------------------------------------
def parse_input() -> dict:
    try:
        user_data = json.loads(sys.argv[1])
        logging.info(f"Received input: {user_data}")
        user_data.pop("user_id", None)
        return user_data
    except Exception as e:
        logging.error(f"Invalid JSON input: {e}")
        print(f"Error: Invalid JSON input - {e}", file=sys.stderr)
        sys.exit(1)

def coerce_int(d: dict, key: str, default=None):
    val = d.get(key, default)
    try:
        return int(val) if val is not None else default
    except Exception:
        return default

def coerce_str(d: dict, key: str, default=""):
    val = d.get(key, default)
    return str(val) if val is not None else default

# -----------------------------------------------------------
# Habit keyword detection
# -----------------------------------------------------------
def detect_habit_type(habit_name: str) -> str:
    habit_name = habit_name.lower()
    for habit_type, keywords in HABIT_KEYWORDS.items():
        if any(k in habit_name for k in keywords):
            return habit_type
    return "general"

# -----------------------------------------------------------
# Feature engineering
# -----------------------------------------------------------
def derive_features(d: dict) -> dict:
    return {
        "age": coerce_int(d, "age", 30),
        "procrastination": coerce_int(d, "procrastination_level", 5),
        "motivation": coerce_int(d, "motivation_level", 5),
        "fatigue": coerce_int(d, "fatigue_level", 5),
        "sleep_hours": coerce_int(d, "sleep_hours", 7),
        "task_complexity": coerce_int(d, "task_complexity", 5),
        "habits_count": coerce_int(d, "current_habits_count", 1),
        "goal_clarity": coerce_int(d, "goal_clarity", 6),
        "focus_span": coerce_int(d, "focus_span", 25),
        "time_availability": coerce_int(d, "time_availability", 60),
        "gender": coerce_str(d, "gender", "Other"),
        "morning_person": coerce_str(d, "morning_person", "0"),
        "habit_name": coerce_str(d, "habit_name", ""),
        "habit_type": detect_habit_type(coerce_str(d, "habit_name", "")),
    }

# -----------------------------------------------------------
# Rule-based scoring
# -----------------------------------------------------------
def score_rules(f: dict) -> Tuple[Dict[str, float], List[Tuple[str, str, float]]]:
    scores = {t: 0.0 for t in T.values()}
    hits = []

    # --- Habit type priority ---
    if f["habit_type"] == "sleep":
        scores[T["TIME_BLOCK"]] += 5.0
        hits.append(("HL1", T["TIME_BLOCK"], 5.0))
    elif f["habit_type"] == "exercise":
        scores[T["TWO_MIN"]] += 3.0
        scores[T["REWARD"]] += 2.0
        hits.append(("HX1", T["TWO_MIN"], 3.0))
        hits.append(("HX2", T["REWARD"], 2.0))
    elif f["habit_type"] == "study":
        scores[T["POMODORO"]] += 2.5
        scores[T["SPACED"]] += 2.0
        hits.append(("HS1", T["POMODORO"], 2.5))
        hits.append(("HS2", T["SPACED"], 2.0))
    elif f["habit_type"] == "nutrition":
        scores[T["INTENT"]] += 2.3
        scores[T["ENVIRONMENT"]] += 2.0
        hits.append(("HN1", T["INTENT"], 2.3))
        hits.append(("HN2", T["ENVIRONMENT"], 2.0))
    elif f["habit_type"] == "mindfulness":
        scores[T["STACK"]] += 2.2
        scores[T["TIME_BLOCK"]] += 2.0
        hits.append(("HM1", T["STACK"], 2.2))
        hits.append(("HM2", T["TIME_BLOCK"], 2.0))

    # --- General rules (existing logic) ---
    if f["procrastination"] >= 7 or f["task_complexity"] >= 7:
        scores[T["EISENHOWER"]] += 2.5
        hits.append(("R1", T["EISENHOWER"], 2.5))
    if f["time_availability"] < 25 or (f["procrastination"] >= 8 and f["motivation"] <= 5):
        scores[T["TWO_MIN"]] += 2.2
        hits.append(("R2", T["TWO_MIN"], 2.2))
    if f["morning_person"] == "1" and f["motivation"] >= 8:
        scores[T["CLUB_5AM"]] += 2.0
        hits.append(("R3", T["CLUB_5AM"], 2.0))
    if f["goal_clarity"] >= 8 and f["time_availability"] >= 90 and f["focus_span"] > 20:
        scores[T["RULE_90901"]] += 2.4
        hits.append(("R4", T["RULE_90901"], 2.4))
    if f["focus_span"] <= 30:
        scores[T["POMODORO"]] += 2.1
        hits.append(("R5", T["POMODORO"], 2.1))
    if f["motivation"] <= 3 or f["fatigue"] >= 7:
        scores[T["REWARD"]] += 2.0
        hits.append(("R6", T["REWARD"], 2.0))

    # Always include a small weight for 2 Minute Rule
    scores[T["TWO_MIN"]] += 0.4
    hits.append(("R12", T["TWO_MIN"], 0.4))

    return scores, hits

# -----------------------------------------------------------
# Pick top techniques
# -----------------------------------------------------------
def pick(scores: Dict[str, float], hits: List[Tuple[str, str, float]]) -> Dict[str, str]:
    if not scores:
        return {"technique": T["TWO_MIN"], "reason": RULE_TEXT["R12"]}

    # Pick technique with highest score
    max_score = max(scores.values())
    candidates = [t for t, s in scores.items() if s == max_score]
    technique = candidates[0]  # deterministic pick

    # Find strongest contributing rule
    contributing = [h for h in hits if h[1] == technique]
    contributing.sort(key=lambda x: x[2], reverse=True)
    primary_rule_id = contributing[0][0] if contributing else "R12"
    reason = RULE_TEXT.get(primary_rule_id, "Personalized recommendation.")

    return {"technique": technique, "reason": reason}
# -----------------------------------------------------------
# Main entry
# -----------------------------------------------------------
def main():
    try:
        data = parse_input()
        f = derive_features(data)
        scores, hits = score_rules(f)
        result = pick(scores, hits)
        logging.info(f"Recommendation: {result}")
        print(json.dumps(result))
    except Exception as e:
        logging.error(f"Error during recommendation: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
