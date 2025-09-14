# predict_technique.py
# Drop-in replacement with richer, weighted rule logic.
import sys
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="C:/Users/gts/habit-tracker/backend/predict_technique.log",
)

def parse_input():
    try:
        user_data = json.loads(sys.argv[1])
        logging.info(f"Received input: {user_data}")
        user_id = user_data.get("user_id")
        if user_id:
            logging.info(f"Processing for user_id: {user_id}")
        # We don’t use user_id for logic—remove to avoid side-effects later
        user_data.pop("user_id", None)
        return user_data
    except Exception as e:
        logging.error(f"Invalid JSON input: {e}")
        print(f"Error: Invalid JSON input - {e}", file=sys.stderr)
        sys.exit(1)

def coerce_int(d, key, default=None):
    val = d.get(key, default)
    try:
        return int(val) if val is not None else default
    except Exception:
        return default

def coerce_str(d, key, default=""):
    val = d.get(key, default)
    return str(val) if val is not None else default

def validate(data):
    required = [
        "age",
        "procrastination_level",
        "motivation_level",
        "fatigue_level",
        "sleep_hours",
        "task_complexity",
        "current_habits_count",
        "goal_clarity",
        "focus_span",
        "time_availability",
        "gender",
        "morning_person",
    ]
    missing = [k for k in required if data.get(k) is None]
    if missing:
        raise ValueError(f"Missing fields: {', '.join(missing)}")

def derive_features(d):
    # Numeric fields
    age               = coerce_int(d, "age", 30)
    procrastination   = coerce_int(d, "procrastination_level", 5) # 1-10
    motivation        = coerce_int(d, "motivation_level", 5)      # 1-10
    fatigue           = coerce_int(d, "fatigue_level", 5)         # 1-10
    sleep_hours       = coerce_int(d, "sleep_hours", 7)           # hours
    task_complexity   = coerce_int(d, "task_complexity", 5)       # 1-10
    habits_count      = coerce_int(d, "current_habits_count", 1)
    goal_clarity      = coerce_int(d, "goal_clarity", 6)          # 1-10
    focus_span        = coerce_int(d, "focus_span", 25)           # minutes
    time_availability = coerce_int(d, "time_availability", 60)    # minutes
    gender            = coerce_str(d, "gender", "Other")
    morning_person    = coerce_str(d, "morning_person", "0")      # "1"/"0"

    # Optional pattern-aware extras (safe if not provided)
    best_hour            = coerce_int(d, "best_hour", None)  # 0-23 if provided
    most_missed_weekday  = coerce_str(d, "most_missed_weekday", "")

    # Derived indicators
    sleep_quality = (
        "low" if sleep_hours < 6 else
        "ok"  if sleep_hours < 8 else
        "high"
    )
    time_pressure = (
        "very_low" if time_availability < 25 else
        "low"      if time_availability < 45 else
        "medium"   if time_availability < 90 else
        "high"
    )
    cognitive_load = (
        "high" if task_complexity >= 7 and fatigue >= 6 else
        "med"  if task_complexity >= 5 else
        "low"
    )
    habit_load = (
        "many" if habits_count >= 4 else
        "some" if habits_count >= 2 else
        "few"
    )
    focus_window = (
        "short"  if focus_span < 20 else
        "medium" if focus_span < 45 else
        "long"
    )

    return {
        "age": age,
        "procrastination": procrastination,
        "motivation": motivation,
        "fatigue": fatigue,
        "sleep_hours": sleep_hours,
        "task_complexity": task_complexity,
        "habits_count": habits_count,
        "goal_clarity": goal_clarity,
        "focus_span": focus_span,
        "time_availability": time_availability,
        "gender": gender,
        "morning_person": morning_person,
        "sleep_quality": sleep_quality,
        "time_pressure": time_pressure,
        "cognitive_load": cognitive_load,
        "habit_load": habit_load,
        "focus_window": focus_window,
        "best_hour": best_hour,
        "most_missed_weekday": most_missed_weekday
    }

# A small registry to keep short “why” texts per rule (shown to user).
RULE_TEXT = {
    "R1": "High procrastination / complex tasks → prioritize with a matrix.",
    "R2": "Very low time or need quick wins → start with tiny actions.",
    "R3": "Morning type with high motivation → leverage early deep work.",
    "R4": "Clear goals and ≥90 min → protect a 90-minute focus block.",
    "R5": "Short focus span with limited time → use 25-minute sprints.",
    "R6": "Low motivation / high fatigue → add rewards to reinforce.",
    "R7": "Managing many habits → chain them together to reduce friction.",
    "R8": "Low sleep/energy → time-block early & include recovery breaks.",
    "R9": "High cognitive load → schedule blocks and reduce context switching.",
    "R10": "Your best hours aren’t morning → plan blocks around your peak.",
    "R11": "High motivation + medium time → deliberate sprints work well.",
    "R12": "Balanced profile → a quick start rule builds momentum.",
}

# Techniques we recommend
# (You already use these across the app.)
T = {
    "EISENHOWER": "Eisenhower Matrix",
    "TWO_MIN": "2 Minute Rule",
    "CLUB_5AM": "5 AM Club",
    "RULE_90901": "90/90/1 Rule",
    "POMODORO": "Pomodoro",
    "REWARD": "Reward and Reinforcement",
    "STACK": "Habit Stacking",
    "TIME_BLOCK": "Time Blocking",
}

def score_rules(f):
    """
    Returns:
      scores: {technique_name: total_weight}
      hits:   list of (rule_id, technique_name, weight)
    """
    scores = {t: 0.0 for t in T.values()}
    hits = []

    # --- Rule R1: Eisenhower for procrastination / complexity ---
    if f["procrastination"] >= 7 or f["task_complexity"] >= 7:
        w = 2.5
        scores[T["EISENHOWER"]] += w
        hits.append(("R1", T["EISENHOWER"], w))

    # --- R2: 2 Minute when time is extremely tight OR very high procrastination ---
    if f["time_pressure"] in ("very_low",) or (f["procrastination"] >= 8 and f["motivation"] <= 5):
        w = 2.2
        scores[T["TWO_MIN"]] += w
        hits.append(("R2", T["TWO_MIN"], w))

    # --- R3: 5 AM Club for morning person with high motivation (and decent sleep) ---
    if f["morning_person"] == "1" and f["motivation"] >= 8 and f["sleep_quality"] != "low":
        w = 2.0
        scores[T["CLUB_5AM"]] += w
        hits.append(("R3", T["CLUB_5AM"], w))

    # --- R4: 90/90/1 for clear goals and ≥90 minutes available ---
    if f["goal_clarity"] >= 8 and f["time_availability"] >= 90 and f["focus_window"] != "short":
        w = 2.4
        scores[T["RULE_90901"]] += w
        hits.append(("R4", T["RULE_90901"], w))

    # --- R5: Pomodoro when focus is short/medium and time is limited ---
    if f["focus_window"] in ("short", "medium") and f["time_pressure"] in ("low", "medium"):
        w = 2.1
        scores[T["POMODORO"]] += w
        hits.append(("R5", T["POMODORO"], w))

    # --- R6: Reward & Reinforcement for low motivation or high fatigue ---
    if f["motivation"] <= 3 or f["fatigue"] >= 7:
        w = 2.0
        scores[T["REWARD"]] += w
        hits.append(("R6", T["REWARD"], w))

    # --- R7: Habit Stacking when juggling many habits ---
    if f["habit_load"] == "many":
        w = 1.8
        scores[T["STACK"]] += w
        hits.append(("R7", T["STACK"], w))

    # --- R8: Time Blocking for low energy / sleep to protect energy ---
    if f["sleep_quality"] == "low" or (f["fatigue"] >= 6 and f["time_availability"] >= 45):
        w = 1.9
        scores[T["TIME_BLOCK"]] += w
        hits.append(("R8", T["TIME_BLOCK"], w))

    # --- R9: Time Blocking for high cognitive load to reduce switching ---
    if f["cognitive_load"] == "high":
        w = 1.6
        scores[T["TIME_BLOCK"]] += w
        hits.append(("R9", T["TIME_BLOCK"], w))

    # --- R10: If best focus hour suggests not morning, avoid 5AM; prefer Time Blocking ---
    if f["best_hour"] is not None and f["best_hour"] >= 12:
        w = 1.4
        scores[T["TIME_BLOCK"]] += w
        hits.append(("R10", T["TIME_BLOCK"], w))

    # --- R11: If motivation high and time medium, Pomodoro often fits well ---
    if f["motivation"] >= 7 and f["time_pressure"] == "medium":
        w = 1.2
        scores[T["POMODORO"]] += w
        hits.append(("R11", T["POMODORO"], w))

    # --- R12: Default gentle start: 2 Minute Rule ---
    # Applied lightly so real signals win; used only if nothing else triggers strongly
    w = 0.4
    scores[T["TWO_MIN"]] += w
    hits.append(("R12", T["TWO_MIN"], w))

    return scores, hits

def pick(scores, hits):
    # Choose highest score; deterministic tie-breaker by our technique order
    order = [
        T["EISENHOWER"],
        T["RULE_90901"],
        T["TIME_BLOCK"],
        T["POMODORO"],
        T["CLUB_5AM"],
        T["STACK"],
        T["REWARD"],
        T["TWO_MIN"],
    ]
    best_score = max(scores.values()) if scores else 0
    candidates = [t for t, s in scores.items() if s == best_score]
    technique = next((t for t in order if t in candidates), candidates[0] if candidates else T["TWO_MIN"])

    # Find the strongest contributing rule for the chosen technique
    contributing = [h for h in hits if h[1] == technique]
    contributing.sort(key=lambda x: x[2], reverse=True)  # by weight
    primary_rule_id = contributing[0][0] if contributing else "R12"
    reason = RULE_TEXT.get(primary_rule_id, "Personalized recommendation.")

    return technique, primary_rule_id, reason

def main():
    try:
        data = parse_input()
        validate(data)
        f = derive_features(data)
        scores, hits = score_rules(f)
        technique, rule_id, reason = pick(scores, hits)
        logging.info(f"Recommendation: {technique} via {rule_id} | scores={scores}")
        print(json.dumps({"technique": technique, "rule_id": rule_id, "reason": reason}))
    except Exception as e:
        logging.error(f"Error during recommendation: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
