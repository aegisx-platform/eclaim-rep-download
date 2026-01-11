#!/usr/bin/env python3
"""
Denial Prediction Model Training Script

Trains a machine learning model to predict claim denial risk using:
- Error codes, service type, DRG codes
- Claim amounts, relative weight
- Fund type and other claim metadata

Uses RandomForest with class weighting to handle imbalanced data (6% denial rate)
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Load .env file
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import (
    classification_report, confusion_matrix,
    precision_recall_fscore_support, roc_auc_score
)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.database import get_db_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Model save path
MODEL_DIR = Path(__file__).parent / 'models'
MODEL_PATH = MODEL_DIR / 'denial_predictor.joblib'
METADATA_PATH = MODEL_DIR / 'model_metadata.json'


def get_db_connection():
    """Get database connection based on config"""
    db_config = get_db_config()
    db_type = os.getenv('DB_TYPE', 'postgresql')

    # Use localhost when running outside Docker (db hostname is for Docker network)
    host = db_config['host']
    if host == 'db':
        host = 'localhost'

    if db_type == 'mysql':
        import pymysql
        return pymysql.connect(
            host=host,
            port=db_config['port'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password']
        )
    else:
        import psycopg2
        return psycopg2.connect(
            host=host,
            port=db_config['port'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password']
        )


def load_training_data():
    """Load claims data from database for training"""
    logger.info("Loading training data from database...")

    conn = get_db_connection()

    # Query to get relevant features for denial prediction
    query = """
    SELECT
        tran_id,
        COALESCE(service_type, 'UN') as service_type,
        COALESCE(error_code, '0') as error_code,
        COALESCE(drg, 'UNKNOWN') as drg,
        COALESCE(main_fund, 'UNKNOWN') as main_fund,
        COALESCE(main_inscl, 'UNKNOWN') as main_inscl,
        COALESCE(ptype, 'UNKNOWN') as ptype,
        COALESCE(claim_drg, 0) as claim_amount,
        COALESCE(rw, 0) as rw,
        COALESCE(adjrw_nhso, 0) as adjrw,
        CASE
            WHEN reimb_nhso > 0 THEN 0  -- Approved (has reimbursement)
            WHEN error_code IS NOT NULL AND error_code != '' AND error_code != '0' THEN 1  -- Denied
            ELSE 0  -- Default to approved
        END as is_denied
    FROM claim_rep_opip_nhso_item
    WHERE claim_drg IS NOT NULL AND claim_drg > 0
    """

    df = pd.read_sql(query, conn)
    conn.close()

    logger.info(f"Loaded {len(df)} records")
    logger.info(f"Denial rate: {df['is_denied'].mean()*100:.2f}%")

    return df


def prepare_features(df):
    """Prepare features for training"""
    logger.info("Preparing features...")

    # Create feature dataframe
    features = df.copy()

    # Encode categorical variables
    label_encoders = {}

    categorical_cols = ['service_type', 'drg', 'main_fund', 'main_inscl', 'ptype']
    for col in categorical_cols:
        le = LabelEncoder()
        features[f'{col}_encoded'] = le.fit_transform(features[col].astype(str))
        label_encoders[col] = le

    # Error code - extract numeric part
    features['error_code_num'] = pd.to_numeric(
        features['error_code'].str.extract(r'(\d+)', expand=False),
        errors='coerce'
    ).fillna(0).astype(int)

    # Create high-risk error code flag (998 is most common denial code)
    features['high_risk_error'] = (features['error_code'].str.contains('998', na=False)).astype(int)

    # Numeric features
    features['claim_amount'] = pd.to_numeric(features['claim_amount'], errors='coerce').fillna(0)
    features['rw'] = pd.to_numeric(features['rw'], errors='coerce').fillna(0)
    features['adjrw'] = pd.to_numeric(features['adjrw'], errors='coerce').fillna(0)

    # Log transform for skewed amount
    features['claim_amount_log'] = np.log1p(features['claim_amount'])

    # Feature columns for model
    feature_cols = [
        'service_type_encoded',
        'drg_encoded',
        'main_fund_encoded',
        'main_inscl_encoded',
        'ptype_encoded',
        'error_code_num',
        'high_risk_error',
        'claim_amount',
        'claim_amount_log',
        'rw',
        'adjrw'
    ]

    X = features[feature_cols]
    y = features['is_denied']

    logger.info(f"Feature shape: {X.shape}")
    logger.info(f"Class distribution: {y.value_counts().to_dict()}")

    return X, y, label_encoders, feature_cols


def train_model(X, y):
    """Train the denial prediction model"""
    logger.info("Training model...")

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    logger.info(f"Training set: {len(X_train)} samples")
    logger.info(f"Test set: {len(X_test)} samples")

    # Calculate class weights for imbalanced data
    denial_rate = y_train.mean()
    class_weight = {0: 1.0, 1: (1 - denial_rate) / denial_rate}
    logger.info(f"Class weights: {class_weight}")

    # Train RandomForest with class weighting
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight=class_weight,
        random_state=42,
        n_jobs=-1
    )

    model.fit(X_train, y_train)

    # Evaluate on test set
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    # Metrics
    logger.info("\n" + "="*50)
    logger.info("MODEL EVALUATION")
    logger.info("="*50)

    logger.info("\nClassification Report:")
    logger.info("\n" + classification_report(y_test, y_pred, target_names=['Approved', 'Denied']))

    logger.info("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    logger.info(f"TN={cm[0,0]}, FP={cm[0,1]}, FN={cm[1,0]}, TP={cm[1,1]}")

    # ROC-AUC
    try:
        auc = roc_auc_score(y_test, y_prob)
        logger.info(f"\nROC-AUC Score: {auc:.4f}")
    except Exception as e:
        auc = 0
        logger.warning(f"Could not calculate AUC: {e}")

    # Feature importance
    logger.info("\nFeature Importance:")
    feature_importance = pd.DataFrame({
        'feature': X.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    for _, row in feature_importance.iterrows():
        logger.info(f"  {row['feature']}: {row['importance']:.4f}")

    # Cross-validation
    logger.info("\nCross-validation scores:")
    cv_scores = cross_val_score(model, X, y, cv=5, scoring='f1')
    logger.info(f"  F1 scores: {cv_scores}")
    logger.info(f"  Mean F1: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

    # Calculate precision, recall, f1 for metadata
    precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average='binary')

    metrics = {
        'accuracy': float((y_pred == y_test).mean()),
        'precision': float(precision),
        'recall': float(recall),
        'f1_score': float(f1),
        'auc_roc': float(auc),
        'cv_f1_mean': float(cv_scores.mean()),
        'cv_f1_std': float(cv_scores.std()),
        'test_size': len(X_test),
        'train_size': len(X_train),
        'denial_rate': float(y.mean()),
        'confusion_matrix': {
            'true_negative': int(cm[0,0]),
            'false_positive': int(cm[0,1]),
            'false_negative': int(cm[1,0]),
            'true_positive': int(cm[1,1])
        }
    }

    return model, metrics, feature_importance


def save_model(model, label_encoders, feature_cols, metrics):
    """Save trained model and metadata"""
    logger.info(f"\nSaving model to {MODEL_PATH}...")

    # Create models directory if not exists
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # Save model bundle
    model_bundle = {
        'model': model,
        'label_encoders': label_encoders,
        'feature_cols': feature_cols,
        'version': '1.0.0'
    }

    joblib.dump(model_bundle, MODEL_PATH)
    logger.info(f"Model saved to {MODEL_PATH}")

    # Save metadata
    metadata = {
        'trained_at': datetime.now().isoformat(),
        'model_type': 'RandomForestClassifier',
        'version': '1.0.0',
        'feature_columns': feature_cols,
        'metrics': metrics
    }

    with open(METADATA_PATH, 'w') as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Metadata saved to {METADATA_PATH}")


def main():
    """Main training pipeline"""
    logger.info("="*60)
    logger.info("DENIAL PREDICTION MODEL TRAINING")
    logger.info("="*60)

    try:
        # Load data
        df = load_training_data()

        if len(df) < 100:
            logger.error("Not enough data for training. Need at least 100 records.")
            return False

        # Prepare features
        X, y, label_encoders, feature_cols = prepare_features(df)

        # Check if we have enough denied cases
        denial_count = y.sum()
        if denial_count < 10:
            logger.warning(f"Only {denial_count} denied cases. Model may not be reliable.")

        # Train model
        model, metrics, feature_importance = train_model(X, y)

        # Save model
        save_model(model, label_encoders, feature_cols, metrics)

        logger.info("\n" + "="*60)
        logger.info("TRAINING COMPLETE")
        logger.info("="*60)
        logger.info(f"Model saved to: {MODEL_PATH}")
        logger.info(f"F1 Score: {metrics['f1_score']:.4f}")
        logger.info(f"AUC-ROC: {metrics['auc_roc']:.4f}")

        return True

    except Exception as e:
        logger.error(f"Training failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
