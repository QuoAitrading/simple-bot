"""
Neural Network Confidence Scorer for Cloud API
Loads your trained neural_model.pth and provides same predictions as backtest
"""
import torch
import torch.nn as nn
import numpy as np
import os
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SignalConfidenceNet(nn.Module):
    """
    Neural network that predicts trade success probability.
    EXACT SAME architecture as dev-tools/neural_confidence_model.py
    """
    
    def __init__(self, input_size=12):
        super(SignalConfidenceNet, self).__init__()
        
        self.network = nn.Sequential(
            # Layer 1: 12 → 64
            nn.Linear(input_size, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            
            # Layer 2: 64 → 32
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            
            # Output: 32 → 1
            nn.Linear(32, 1),
            nn.Sigmoid()  # 0-1 confidence
        )
        
    def forward(self, x):
        return self.network(x)


class NeuralConfidenceScorer:
    """
    Cloud-ready neural network scorer
    Loads your trained model and provides predictions
    """
    
    def __init__(self, model_path: str = "neural_model.pth"):
        self.model = None
        self.model_path = model_path
        self.device = torch.device('cpu')  # Cloud runs on CPU
        
        # Load model if exists
        if os.path.exists(model_path):
            self.load_model()
        else:
            logger.warning(f"⚠️  Neural model not found: {model_path}")
            logger.warning(f"   Will use pattern matching fallback")
    
    def load_model(self):
        """Load trained neural network"""
        try:
            self.model = SignalConfidenceNet(input_size=12)
            self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
            self.model.eval()  # Set to evaluation mode
            logger.info(f"✅ Neural model loaded: {self.model_path}")
        except Exception as e:
            logger.error(f"❌ Failed to load neural model: {e}")
            self.model = None
    
    def prepare_features(self, state: Dict) -> np.ndarray:
        """
        Convert market state to neural network input features
        EXACT SAME features as backtest (12 features)
        """
        features = [
            state.get('rsi', 50.0),                          # 0: RSI
            state.get('vwap_distance', 0.0),                 # 1: VWAP distance
            state.get('vix', 15.0),                          # 2: VIX
            state.get('spread_ticks', 1.0),                  # 3: Spread
            state.get('hour', 12),                           # 4: Hour of day
            state.get('day_of_week', 2),                     # 5: Day of week
            state.get('volume_ratio', 1.0),                  # 6: Volume ratio
            state.get('atr', 10.0),                          # 7: ATR
            state.get('recent_pnl', 0.0),                    # 8: Recent P&L
            state.get('streak', 0),                          # 9: Win/loss streak
            state.get('signal_long', 0),                     # 10: LONG signal (1/0)
            state.get('signal_short', 0),                    # 11: SHORT signal (1/0)
        ]
        
        return np.array(features, dtype=np.float32)
    
    def predict(self, state: Dict, signal: str) -> Dict:
        """
        Get neural network prediction
        
        Args:
            state: Market state dict with RSI, VWAP, VIX, etc.
            signal: 'LONG' or 'SHORT'
        
        Returns:
            Dict with confidence, should_trade, reason
        """
        if self.model is None:
            # Fallback to pattern matching if no model
            return {
                'confidence': 0.5,
                'should_trade': False,
                'size_multiplier': 1.0,
                'reason': 'Neural model not loaded, using fallback',
                'model_used': 'fallback'
            }
        
        try:
            # Set signal direction (one-hot encoding)
            state['signal_long'] = 1 if signal == 'LONG' else 0
            state['signal_short'] = 1 if signal == 'SHORT' else 0
            
            # Prepare features
            features = self.prepare_features(state)
            
            # Convert to tensor
            x = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
            
            # Get prediction
            with torch.no_grad():
                confidence = self.model(x).item()
            
            # Apply temperature scaling (same as backtest)
            temperature = 1.0
            confidence = confidence ** (1.0 / temperature)
            
            # Cap at 95% (never 100% confident)
            confidence = min(confidence, 0.95)
            
            # Decision threshold (same as backtest)
            threshold = 0.5  # User configurable
            should_trade = confidence >= threshold
            
            # Size multiplier based on confidence (same as backtest)
            if confidence >= 0.85:
                size_mult = 1.5  # Very confident
            elif confidence >= 0.70:
                size_mult = 1.25  # Confident
            elif confidence >= 0.55:
                size_mult = 1.0  # Normal
            else:
                size_mult = 0.75  # Less confident
            
            reason = f"Neural network: {confidence:.1%} confidence (threshold: {threshold:.0%})"
            
            return {
                'confidence': confidence,
                'should_trade': should_trade,
                'size_multiplier': size_mult,
                'reason': reason,
                'model_used': 'neural_network',
                'threshold': threshold
            }
            
        except Exception as e:
            logger.error(f"❌ Neural prediction error: {e}")
            return {
                'confidence': 0.5,
                'should_trade': False,
                'size_multiplier': 1.0,
                'reason': f'Error: {str(e)}',
                'model_used': 'error'
            }


# Global neural scorer instance (loaded once at startup)
neural_scorer: Optional[NeuralConfidenceScorer] = None


def init_neural_scorer(model_path: str = "neural_model.pth"):
    """Initialize neural scorer at API startup"""
    global neural_scorer
    neural_scorer = NeuralConfidenceScorer(model_path)
    return neural_scorer


def get_neural_prediction(state: Dict, signal: str) -> Dict:
    """
    Get neural network prediction (convenience function)
    
    Args:
        state: Market state with RSI, VWAP, VIX, etc.
        signal: 'LONG' or 'SHORT'
    
    Returns:
        Dict with confidence, should_trade, size_multiplier, reason
    """
    global neural_scorer
    
    if neural_scorer is None:
        init_neural_scorer()
    
    return neural_scorer.predict(state, signal)
