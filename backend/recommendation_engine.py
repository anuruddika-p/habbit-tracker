import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import joblib
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load dataset
try:
    df = pd.read_csv('C:/Users/gts/habit-tracker/backend/productivity_habit_dataset.csv')
except FileNotFoundError as e:
    logging.error(f"CSV file not found: {e}")
    exit(1)

# Drop rows with missing target
df = df.dropna(subset=['recommended_technique'])
logging.info(f"Loaded dataset with {len(df)} rows.")

# Preprocess categorical variables
le_gender = LabelEncoder()
df['gender'] = le_gender.fit_transform(df['gender'])

le_morning = LabelEncoder()
df['morning_person'] = le_morning.fit_transform(df['morning_person'].astype(str))  # Ensure string for consistency

le_target = LabelEncoder()
df['recommended_technique'] = le_target.fit_transform(df['recommended_technique'])

# Define features and target
X = df.drop('recommended_technique', axis=1)
y = df['recommended_technique']

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
logging.info(f"Training set: {len(X_train)} rows, Test set: {len(X_test)} rows")

# Train model
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Evaluate on training set
y_train_pred = model.predict(X_train)
train_accuracy = accuracy_score(y_train, y_train_pred)
logging.info(f"Training Accuracy: {train_accuracy:.2f}")

# Evaluate on test set
y_test_pred = model.predict(X_test)
test_accuracy = accuracy_score(y_test, y_test_pred)
logging.info(f"Test Accuracy: {test_accuracy:.2f}")

# Detailed report
logging.info("\nClassification Report (Test Set):")
print(classification_report(y_test, y_test_pred, labels=np.arange(len(le_target.classes_)), target_names=le_target.classes_, zero_division=0))

# Confusion matrix
logging.info("\nConfusion Matrix (Test Set):")
cm = confusion_matrix(y_test, y_test_pred)
logging.info(f"\n{cm}")

# Check for underfitting/overfitting
if train_accuracy < 0.7:
    logging.warning("Possible underfitting: Training accuracy is low (<0.7)")
elif (train_accuracy - test_accuracy) > 0.1:
    logging.warning(f"Possible overfitting: Large gap between training ({train_accuracy:.2f}) and test ({test_accuracy:.2f}) accuracy")
else:
    logging.info("Model appears to have a good fit")

# Save model and encoders
joblib.dump(model, 'recommendation_model.pkl')
joblib.dump(le_gender, 'le_gender.pkl')
joblib.dump(le_morning, 'le_morning.pkl')
joblib.dump(le_target, 'le_target.pkl')
logging.info("Model and encoders saved.")