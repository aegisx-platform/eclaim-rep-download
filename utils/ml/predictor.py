#!/usr/bin/env python3
"""
Denial Prediction Module

Loads trained model and provides prediction functions for the API
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np
import joblib

logger = logging.getLogger(__name__)

# Model paths
MODEL_DIR = Path(__file__).parent / 'models'
MODEL_PATH = MODEL_DIR / 'denial_predictor.joblib'
METADATA_PATH = MODEL_DIR / 'model_metadata.json'


class DenialPredictor:
    """Denial prediction using trained ML model"""

    def __init__(self):
        self.model = None
        self.label_encoders = None
        self.feature_cols = None
        self.metadata = None
        self.is_loaded = False

    def load_model(self) -> bool:
        """Load the trained model"""
        try:
            if not MODEL_PATH.exists():
                logger.warning(f"Model file not found: {MODEL_PATH}")
                return False

            # Load model bundle
            bundle = joblib.load(MODEL_PATH)
            self.model = bundle['model']
            self.label_encoders = bundle['label_encoders']
            self.feature_cols = bundle['feature_cols']

            # Load metadata
            if METADATA_PATH.exists():
                with open(METADATA_PATH) as f:
                    self.metadata = json.load(f)

            self.is_loaded = True
            logger.info("Model loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

    def _prepare_features(self, data: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """Prepare features from input data"""
        try:
            # Create dataframe with single row
            features = pd.DataFrame([{
                'service_type': str(data.get('service_type', 'UN')),
                'drg': str(data.get('drg', 'UNKNOWN')),
                'main_fund': str(data.get('main_fund', 'UNKNOWN')),
                'main_inscl': str(data.get('main_inscl', 'UNKNOWN')),
                'ptype': str(data.get('ptype', 'UNKNOWN')),
                'error_code': str(data.get('error_code', '0')),
                'claim_amount': float(data.get('claim_amount', 0)),
                'rw': float(data.get('rw', 0)),
                'adjrw': float(data.get('adjrw', 0))
            }])

            # Encode categorical variables
            for col in ['service_type', 'drg', 'main_fund', 'main_inscl', 'ptype']:
                encoder = self.label_encoders.get(col)
                if encoder:
                    # Handle unseen labels
                    value = features[col].iloc[0]
                    if value in encoder.classes_:
                        features[f'{col}_encoded'] = encoder.transform(features[col])
                    else:
                        # Use -1 for unknown categories
                        features[f'{col}_encoded'] = -1
                else:
                    features[f'{col}_encoded'] = 0

            # Error code numeric extraction
            error_code = features['error_code'].iloc[0]
            import re
            match = re.search(r'(\d+)', str(error_code))
            features['error_code_num'] = int(match.group(1)) if match else 0

            # High risk error flag
            features['high_risk_error'] = 1 if '998' in str(error_code) else 0

            # Log transform
            features['claim_amount_log'] = np.log1p(features['claim_amount'])

            # Select only model features
            X = features[self.feature_cols]
            return X

        except Exception as e:
            logger.error(f"Feature preparation failed: {e}")
            return None

    def predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict denial risk for a single claim

        Args:
            data: Dictionary with claim attributes:
                - service_type: 'OP' or 'IP'
                - drg: DRG code
                - fund: Fund type
                - error_code: Error code (if any)
                - claim_amount: Amount claimed
                - rw: Relative weight
                - los: Length of stay

        Returns:
            Dictionary with prediction results
        """
        if not self.is_loaded:
            if not self.load_model():
                return {
                    'error': 'Model not loaded',
                    'risk_score': 0.5,
                    'risk_level': 'unknown',
                    'confidence': 0
                }

        try:
            X = self._prepare_features(data)
            if X is None:
                return {
                    'error': 'Feature preparation failed',
                    'risk_score': 0.5,
                    'risk_level': 'unknown',
                    'confidence': 0
                }

            # Predict probability
            proba = self.model.predict_proba(X)[0]
            denial_prob = float(proba[1])

            # Determine risk level
            if denial_prob >= 0.7:
                risk_level = 'high'
            elif denial_prob >= 0.4:
                risk_level = 'medium'
            else:
                risk_level = 'low'

            # Calculate confidence (how sure the model is)
            confidence = float(max(proba))

            # Get top contributing factors
            factors = self._get_risk_factors(X, denial_prob)

            return {
                'risk_score': round(denial_prob, 4),
                'risk_level': risk_level,
                'confidence': round(confidence, 4),
                'factors': factors,
                'model_version': self.metadata.get('version', '1.0.0') if self.metadata else '1.0.0'
            }

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return {
                'error': str(e),
                'risk_score': 0.5,
                'risk_level': 'unknown',
                'confidence': 0
            }

    def _get_risk_factors(self, X: pd.DataFrame, denial_prob: float) -> List[Dict[str, str]]:
        """Identify key risk factors for this prediction"""
        factors = []

        try:
            # Get feature importances
            importances = dict(zip(self.feature_cols, self.model.feature_importances_))

            # Check high risk error
            if X['high_risk_error'].iloc[0] == 1:
                factors.append({
                    'factor': 'High Risk Error Code',
                    'description': 'Error code 998 detected (72% denial rate)',
                    'impact': 'high'
                })

            # Check claim amount
            claim_amt = X['claim_amount'].iloc[0]
            if claim_amt < 3500 and claim_amt > 0:
                factors.append({
                    'factor': 'Low Claim Amount',
                    'description': f'Amount {claim_amt:,.0f} is below average',
                    'impact': 'medium'
                })

            # Check RW
            rw = X['rw'].iloc[0]
            if rw < 0.5 and rw > 0:
                factors.append({
                    'factor': 'Low Relative Weight',
                    'description': f'RW {rw:.2f} indicates lower complexity',
                    'impact': 'low'
                })

            # If high probability but no specific factors
            if denial_prob > 0.5 and len(factors) == 0:
                factors.append({
                    'factor': 'Pattern Match',
                    'description': 'Claim matches historical denial patterns',
                    'impact': 'medium'
                })

        except Exception as e:
            logger.error(f"Failed to get risk factors: {e}")

        return factors

    def predict_batch(self, claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Predict denial risk for multiple claims"""
        return [self.predict(claim) for claim in claims]

    def get_model_info(self) -> Dict[str, Any]:
        """Get model metadata and performance info"""
        if not self.is_loaded:
            self.load_model()

        if self.metadata:
            return {
                'trained_at': self.metadata.get('trained_at'),
                'model_type': self.metadata.get('model_type'),
                'version': self.metadata.get('version'),
                'metrics': self.metadata.get('metrics', {}),
                'is_available': True
            }
        else:
            return {
                'is_available': False,
                'message': 'Model not trained yet'
            }


# Singleton instance
_predictor = None


def get_predictor() -> DenialPredictor:
    """Get or create predictor singleton"""
    global _predictor
    if _predictor is None:
        _predictor = DenialPredictor()
    return _predictor


def predict_denial_risk(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function for single prediction"""
    return get_predictor().predict(data)


def predict_denial_risk_batch(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convenience function for batch prediction"""
    return get_predictor().predict_batch(claims)


def get_model_info() -> Dict[str, Any]:
    """Get model information"""
    return get_predictor().get_model_info()
