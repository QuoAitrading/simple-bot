"""
Session State Manager
====================
Tracks bot performance across sessions to provide smart warnings and recommendations.
"""

import json
import os
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class SessionStateManager:
    """Manages session state to track bot performance across restarts."""
    
    def __init__(self, state_file: str = "data/session_state.json"):
        """Initialize session state manager."""
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self.load_state()
    
    def load_state(self) -> Dict[str, Any]:
        """Load session state from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    logger.info(f"Loaded session state from {self.state_file}")
                    return state
            except Exception as e:
                logger.error(f"Failed to load session state: {e}")
        
        # Return default state
        return self._default_state()
    
    def _default_state(self) -> Dict[str, Any]:
        """Return default session state."""
        return {
            "last_updated": datetime.now().isoformat(),
            "trading_date": date.today().isoformat(),
            "starting_equity": None,
            "current_equity": None,
            "peak_equity": None,
            "daily_pnl": 0.0,
            "daily_trades": 0,
            "total_trades_today": 0,
            "current_drawdown_percent": 0.0,
            "daily_loss_percent": 0.0,
            "approaching_failure": False,
            "in_recovery_mode": False,
            "warnings": [],
            "recommendations": [],
            "account_type": None,
            "broker": None,
            "max_drawdown_limit": None,
            "daily_loss_limit": None,
        }
    
    def save_state(self):
        """Save session state to disk."""
        try:
            self.state["last_updated"] = datetime.now().isoformat()
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2)
            logger.debug(f"Saved session state to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save session state: {e}")
    
    def update_trading_state(
        self,
        starting_equity: float,
        current_equity: float,
        daily_pnl: float,
        daily_trades: int,
        broker: str,
        account_type: str = None
    ):
        """Update current trading state."""
        today = date.today().isoformat()
        
        # Reset if new trading day
        if self.state["trading_date"] != today:
            self.state = self._default_state()
            self.state["trading_date"] = today
        
        self.state["starting_equity"] = starting_equity
        self.state["current_equity"] = current_equity
        self.state["daily_pnl"] = daily_pnl
        self.state["total_trades_today"] = daily_trades
        self.state["broker"] = broker
        self.state["account_type"] = account_type or self._infer_account_type(broker)
        
        # Update peak equity
        if self.state["peak_equity"] is None or current_equity > self.state["peak_equity"]:
            self.state["peak_equity"] = current_equity
        
        # Calculate metrics
        if starting_equity > 0:
            self.state["current_drawdown_percent"] = ((starting_equity - current_equity) / starting_equity) * 100
            self.state["daily_loss_percent"] = (abs(daily_pnl) / starting_equity) * 100 if daily_pnl < 0 else 0.0
        
        self.save_state()
    
    def _infer_account_type(self, broker: str) -> str:
        """Infer account type from broker name."""
        prop_firms = ["topstep", "apex", "earn2trade", "ftmo", "the5ers"]
        broker_lower = broker.lower()
        
        for prop_firm in prop_firms:
            if prop_firm in broker_lower:
                return "prop_firm"
        
        return "live_broker"
    
    def check_warnings_and_recommendations(
        self,
        account_size: float,
        max_drawdown_percent: float,
        daily_loss_limit: float,
        current_confidence: float,
        max_contracts: int,
        recovery_mode_enabled: bool
    ) -> Tuple[list, list, Dict[str, Any]]:
        """
        Check current state and generate warnings/recommendations.
        
        Returns:
            Tuple of (warnings, recommendations, smart_settings)
        """
        warnings = []
        recommendations = []
        smart_settings = {}
        
        current_equity = self.state.get("current_equity", account_size)
        daily_pnl = self.state.get("daily_pnl", 0.0)
        current_drawdown = self.state.get("current_drawdown_percent", 0.0)
        daily_loss_pct = self.state.get("daily_loss_percent", 0.0)
        account_type = self.state.get("account_type", "live_broker")
        broker = self.state.get("broker", "Unknown")
        
        # Calculate approaching threshold
        daily_loss_severity = abs(daily_pnl) / daily_loss_limit if daily_loss_limit > 0 else 0.0
        drawdown_severity = current_drawdown / max_drawdown_percent if max_drawdown_percent > 0 else 0.0
        max_severity = max(daily_loss_severity, drawdown_severity)
        
        # Check if approaching failure (80%+ of limits)
        approaching_failure = max_severity >= 0.80
        critical_failure = max_severity >= 0.95
        
        self.state["approaching_failure"] = approaching_failure
        self.state["in_recovery_mode"] = recovery_mode_enabled
        
        # Generate warnings
        if critical_failure:
            warnings.append({
                "level": "critical",
                "message": f"⚠️ CRITICAL: At {max_severity*100:.0f}% of account limits! Account failure imminent!"
            })
        elif approaching_failure:
            warnings.append({
                "level": "warning",
                "message": f"⚠️ WARNING: Approaching limits ({max_severity*100:.0f}% of max). Consider enabling Recovery Mode."
            })
        
        if daily_loss_pct > 1.5 and account_type == "prop_firm":
            warnings.append({
                "level": "warning",
                "message": f"Daily loss at {daily_loss_pct:.1f}% of account. Prop firm accounts have strict rules."
            })
        
        # Generate recommendations based on account type and state
        if approaching_failure:
            if not recovery_mode_enabled:
                recommendations.append({
                    "priority": "high",
                    "message": "🔄 RECOMMEND: Enable Recovery Mode to attempt recovery with high-confidence signals"
                })
            
            # Recommend higher confidence
            if max_severity >= 0.90:
                recommended_confidence = 85.0
            elif max_severity >= 0.80:
                recommended_confidence = 75.0
            else:
                recommended_confidence = current_confidence
            
            if recommended_confidence > current_confidence:
                recommendations.append({
                    "priority": "high",
                    "message": f"📊 RECOMMEND: Increase confidence threshold to {recommended_confidence:.0f}% (currently {current_confidence:.0f}%)"
                })
                smart_settings["confidence_threshold"] = recommended_confidence
            
            # Recommend fewer contracts
            if max_severity >= 0.95:
                recommended_contracts = max(1, int(max_contracts * 0.33))
            elif max_severity >= 0.90:
                recommended_contracts = max(1, int(max_contracts * 0.50))
            elif max_severity >= 0.80:
                recommended_contracts = max(1, int(max_contracts * 0.75))
            else:
                recommended_contracts = max_contracts
            
            if recommended_contracts < max_contracts:
                recommendations.append({
                    "priority": "high",
                    "message": f"📉 RECOMMEND: Reduce contracts to {recommended_contracts} (currently {max_contracts})"
                })
                smart_settings["max_contracts"] = recommended_contracts
        
        # Account-type specific recommendations
        if account_type == "prop_firm":
            # Calculate optimal daily loss limit for prop firm
            if account_size > 0:
                # Most prop firms have 2% daily loss rule
                optimal_daily_loss = account_size * 0.02
                if abs(optimal_daily_loss - daily_loss_limit) > 100:
                    recommendations.append({
                        "priority": "medium",
                        "message": f"💡 SUGGEST: Set daily loss limit to ${optimal_daily_loss:.0f} (2% rule for {broker})"
                    })
                    smart_settings["daily_loss_limit"] = optimal_daily_loss
                
                # Recommend trailing drawdown for prop firms
                recommendations.append({
                    "priority": "medium",
                    "message": "🛡️ SUGGEST: Enable trailing drawdown protection for prop firm accounts"
                })
        
        # Save warnings and recommendations to state
        self.state["warnings"] = warnings
        self.state["recommendations"] = recommendations
        self.save_state()
        
        return warnings, recommendations, smart_settings
    
    def is_new_trading_day(self) -> bool:
        """Check if this is a new trading day."""
        return self.state["trading_date"] != date.today().isoformat()
    
    def reset_daily_state(self):
        """Reset daily tracking (called at start of new trading day)."""
        self.state["daily_pnl"] = 0.0
        self.state["daily_trades"] = 0
        self.state["total_trades_today"] = 0
        self.state["daily_loss_percent"] = 0.0
        self.state["trading_date"] = date.today().isoformat()
        self.state["warnings"] = []
        self.state["recommendations"] = []
        self.state["approaching_failure"] = False
        self.save_state()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get current session summary."""
        return {
            "trading_date": self.state.get("trading_date"),
            "current_equity": self.state.get("current_equity"),
            "daily_pnl": self.state.get("daily_pnl"),
            "total_trades_today": self.state.get("total_trades_today"),
            "current_drawdown_percent": self.state.get("current_drawdown_percent"),
            "approaching_failure": self.state.get("approaching_failure"),
            "in_recovery_mode": self.state.get("in_recovery_mode"),
            "account_type": self.state.get("account_type"),
            "broker": self.state.get("broker"),
        }
