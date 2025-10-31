"""
Pure Experience-Based Learning Brain with Reinforcement Learning
=================================================================
The bot learns like a HUMAN TRADER - pure experience with feedback.

How Reinforcement Learning Works:
1. Try action → Get reward (profit) or punishment (loss)
2. Remember: "Action A in State S gave me reward R"
3. Over time: Actions with positive rewards get reinforced
4. Actions with negative rewards get avoided

This is EXACTLY how humans learn:
- Touch hot stove → Pain → Never touch again
- Good trade setup → Profit → Do it again
- Bad entry → Loss → Avoid that pattern

NO PARAMETERS. NO ASSUMPTIONS. PURE TRIAL AND ERROR.

Goal: Maximize cumulative reward (profit) through experience.
"""

import logging
import json
import os
import random
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


class LearningBrain:
    """
    Reinforcement learning brain - learns through reward and punishment.
    
    Phase 1 (0-500 trades): EXPLORATION - Try random things, get feedback
    Phase 2 (500-2000 trades): LEARNING - Favor what worked, still explore
    Phase 3 (2000+ trades): EXPLOITATION - Do what makes money
    """
    
    def __init__(self, config: Dict, knowledge_file: str = "trading_experience.json"):
        """
        Initialize the reinforcement learning brain.
        
        Args:
            config: Bot configuration
            knowledge_file: File to save all experiences
        """
        self.config = config
        self.knowledge_file = knowledge_file
        
        # 🧠 EXPERIENCE DATABASE - Every (state, action, reward) tuple
        self.experiences = []  # List of experiences
        self.total_trades = 0
        
        # 📊 PERFORMANCE TRACKING - Know when to change strategy
        self.recent_rewards = []  # Last 50 trades
        self.losing_streak = 0
        self.winning_streak = 0
        self.consecutive_losses_threshold = 5  # Force exploration after 5 losses
        
        # Learning phases
        self.EXPLORATION_TRADES = 500  # First 500: pure random
        self.LEARNING_TRADES = 2000  # 500-2000: blend
        
        # Exploration rate (epsilon-greedy)
        self.exploration_rate = 1.0  # Start at 100% exploration
        self.min_exploration_rate = 0.1  # Never go below 10% exploration
        self.exploration_decay = 0.995  # Slowly reduce exploration
        
        # Load previous experiences
        self.load_experiences()
        
        logger.info(f"🧠 Reinforcement Learning Brain Initialized:")
        logger.info(f"   Total experiences: {len(self.experiences)}")
        logger.info(f"   Total trades: {self.total_trades}")
        logger.info(f"   Exploration rate: {self.exploration_rate*100:.1f}%")
        
        # Calculate performance metrics
        if self.experiences:
            recent = self.experiences[-50:] if len(self.experiences) > 50 else self.experiences
            wins = sum(1 for exp in recent if exp['outcome']['pnl'] > 0)
            win_rate = (wins / len(recent)) * 100
            avg_pnl = sum(exp['outcome']['pnl'] for exp in recent) / len(recent)
            logger.info(f"   Recent win rate: {win_rate:.1f}%")
            logger.info(f"   Recent avg P&L: ${avg_pnl:.2f}")
    
    def capture_market_state(self, rsi: float, vwap_distance: float, 
                            market_condition: str, volume_ratio: float,
                            trend: str, hour: int, minute: int,
                            day_of_week: int, recent_pnl: float = 0,
                            volatility: str = "medium") -> Dict:
        """Capture complete market state snapshot."""
        return {
            "rsi": round(rsi, 1),
            "vwap_distance": round(vwap_distance, 2),
            "market_condition": market_condition,
            "volume_ratio": round(volume_ratio, 2),
            "trend": trend,
            "time_of_day": f"{hour:02d}:{minute:02d}",
            "hour": hour,
            "day_of_week": day_of_week,
            "recent_pnl": round(recent_pnl, 2),
            "volatility": volatility,
            "timestamp": datetime.now().isoformat()
        }
    
    def decide_action(self, market_state: Dict) -> Dict:
        """
        Decide action using epsilon-greedy exploration.
        
        This is the KEY to reinforcement learning:
        - Sometimes explore (try random stuff)
        - Sometimes exploit (do what worked before)
        - Balance shifts from exploration → exploitation over time
        """
        # 🔥 FORCE EXPLORATION after losing streak
        if self.losing_streak >= self.consecutive_losses_threshold:
            logger.warning(f"💥 LOSING STREAK: {self.losing_streak} losses! Forcing exploration")
            return self._random_action()
        
        # Epsilon-greedy: explore vs exploit
        if random.random() < self.exploration_rate:
            # EXPLORE: Try something random
            logger.info(f"🎲 Exploring (ε={self.exploration_rate:.2%})")
            return self._random_action()
        else:
            # EXPLOIT: Use what we learned
            return self._best_known_action(market_state)
    
    def _random_action(self) -> Dict:
        """Generate random action (exploration)."""
        return {
            "take_trade": random.choice([True, False]),
            "direction": random.choice(["long", "short"]),
            "stop_distance_ticks": random.randint(5, 25),
            "target_distance_ticks": random.randint(10, 100),
            "risk_per_trade": round(random.uniform(0.005, 0.025), 4),
            "stop_buffer_ticks": random.randint(1, 5),
            "breakeven_threshold_ticks": random.randint(5, 15),
            "breakeven_offset_ticks": random.randint(1, 3),
            "trailing_distance_ticks": random.randint(5, 20),
            "trailing_min_profit_ticks": random.randint(8, 20),
            "use_time_tightening": random.choice([True, False]),
            "partial_exit_1_r": round(random.uniform(1.5, 3.0), 1),
            "partial_exit_1_pct": round(random.uniform(0.3, 0.7), 2),
            "partial_exit_2_r": round(random.uniform(2.5, 5.0), 1),
            "partial_exit_2_pct": round(random.uniform(0.2, 0.5), 2),
            "decision_type": "exploration"
        }
    
    def _best_known_action(self, market_state: Dict) -> Dict:
        """
        Find best action based on past rewards (exploitation).
        
        Reinforcement Learning Logic:
        1. Find similar past states
        2. Calculate expected reward for each action type
        3. Choose action with highest expected reward
        4. If no data, explore randomly
        """
        similar = self.find_similar_experiences(market_state, top_n=100)
        
        if len(similar) < 10:
            # Not enough data - explore
            logger.info(f"❓ Insufficient data ({len(similar)} similar) - exploring")
            return self._random_action()
        
        # Calculate expected reward for each action we've seen
        action_rewards = defaultdict(list)
        
        for exp in similar:
            action = exp['action']
            reward = exp['outcome']['pnl']
            
            # Create action signature (direction + stop range + target range)
            direction = action.get('direction', 'unknown')
            stop_range = int(action.get('stop_distance_ticks', 10) / 5) * 5  # Round to 5s
            target_range = int(action.get('target_distance_ticks', 20) / 10) * 10  # Round to 10s
            
            action_sig = f"{direction}_stop{stop_range}_target{target_range}"
            action_rewards[action_sig].append({
                'reward': reward,
                'action': action
            })
        
        # Find action with highest average reward
        best_action_sig = None
        best_avg_reward = float('-inf')
        best_action_data = None
        
        for action_sig, rewards in action_rewards.items():
            avg_reward = sum(r['reward'] for r in rewards) / len(rewards)
            
            if avg_reward > best_avg_reward and len(rewards) >= 3:  # Need at least 3 samples
                best_avg_reward = avg_reward
                best_action_sig = action_sig
                # Use most recent action with this signature
                best_action_data = rewards[-1]['action']
        
        if best_action_data is None:
            # No confident action found
            logger.info(f"💭 No clear winner in {len(similar)} experiences - exploring")
            return self._random_action()
        
        # Found best action!
        action = best_action_data.copy()
        action['decision_type'] = "exploitation"
        action['similar_trades'] = len(similar)
        action['expected_reward'] = best_avg_reward
        action['action_signature'] = best_action_sig
        
        logger.info(f"✅ EXPLOIT: {best_action_sig} (expected ${best_avg_reward:.2f} from {len(action_rewards[best_action_sig])} samples)")
        
        return action
    
    def find_similar_experiences(self, current_state: Dict, top_n: int = 100) -> List[Dict]:
        """Find similar past market states."""
        if not self.experiences:
            return []
        
        similar = []
        
        for exp in self.experiences:
            past_state = exp['state']
            
            # Calculate similarity score
            similarity = 0
            factors = 0
            
            # RSI similarity (within 10 points for more matches)
            if abs(past_state['rsi'] - current_state['rsi']) <= 10:
                similarity += 1
            factors += 1
            
            # VWAP distance similarity (within 0.5 stdev)
            if abs(past_state['vwap_distance'] - current_state['vwap_distance']) <= 0.5:
                similarity += 1
            factors += 1
            
            # Market condition match (important!)
            if past_state['market_condition'] == current_state['market_condition']:
                similarity += 1.5  # Weight this heavily
            factors += 1
            
            # Volume similarity (within 50%)
            if abs(past_state['volume_ratio'] - current_state['volume_ratio']) <= 0.5:
                similarity += 0.5
            factors += 1
            
            # Trend match (important!)
            if past_state['trend'] == current_state['trend']:
                similarity += 1
            factors += 1
            
            # Time similarity (within 2 hours)
            if abs(past_state['hour'] - current_state['hour']) <= 2:
                similarity += 0.5
            factors += 1
            
            # Volatility match
            if past_state['volatility'] == current_state['volatility']:
                similarity += 0.5
            factors += 1
            
            # Calculate final similarity
            similarity_score = similarity / factors
            
            # Include if somewhat similar (>50%)
            if similarity_score >= 0.5:
                exp_copy = exp.copy()
                exp_copy['similarity_score'] = similarity_score
                similar.append(exp_copy)
        
        # Sort by similarity
        similar.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        return similar[:top_n]
    
    def record_experience(self, market_state: Dict, action: Dict, outcome: Dict) -> None:
        """
        Record experience and UPDATE LEARNING based on reward/punishment.
        
        This is CRITICAL for reinforcement learning:
        - Positive reward (profit) → Reinforce this action
        - Negative reward (loss) → Avoid this action
        - Update exploration rate based on performance
        """
        reward = outcome.get('pnl', 0)
        win = outcome.get('win', False)
        
        # Save experience
        experience = {
            "id": len(self.experiences) + 1,
            "timestamp": datetime.now().isoformat(),
            "state": market_state,
            "action": action,
            "outcome": outcome,
            "reward": reward  # Key for RL!
        }
        
        self.experiences.append(experience)
        self.total_trades += 1
        self.recent_rewards.append(reward)
        if len(self.recent_rewards) > 50:
            self.recent_rewards.pop(0)
        
        # 🎯 UPDATE STREAKS (feedback mechanism)
        if win:
            self.winning_streak += 1
            self.losing_streak = 0
            logger.info(f"✅ WIN: ${reward:.2f} (streak: {self.winning_streak})")
        else:
            self.losing_streak += 1
            self.winning_streak = 0
            logger.warning(f"❌ LOSS: ${reward:.2f} (streak: {self.losing_streak})")
        
        # 🔧 ADAPT EXPLORATION RATE based on performance
        if len(self.recent_rewards) >= 10:
            recent_avg = sum(self.recent_rewards[-10:]) / 10
            
            if recent_avg < -50:
                # Losing badly → EXPLORE MORE!
                self.exploration_rate = min(0.5, self.exploration_rate * 1.1)
                logger.warning(f"📉 Poor performance → Increased exploration to {self.exploration_rate:.2%}")
            
            elif recent_avg > 100:
                # Winning → Can exploit more
                self.exploration_rate = max(self.min_exploration_rate, self.exploration_rate * self.exploration_decay)
                logger.info(f"📈 Good performance → Reduced exploration to {self.exploration_rate:.2%}")
            
            else:
                # Normal decay
                self.exploration_rate = max(self.min_exploration_rate, self.exploration_rate * self.exploration_decay)
        
        # Save periodically
        if self.total_trades % 10 == 0:
            self.save_experiences()
            logger.info(f"💾 Saved {len(self.experiences)} experiences (exploration: {self.exploration_rate:.1%})")
    
    def load_experiences(self) -> None:
        """Load previous experiences."""
        if not os.path.exists(self.knowledge_file):
            logger.info("📖 No previous experiences - starting fresh")
            return
        
        try:
            with open(self.knowledge_file, 'r') as f:
                data = json.load(f)
                self.experiences = data.get('experiences', [])
                self.total_trades = data.get('total_trades', 0)
                self.exploration_rate = data.get('exploration_rate', 1.0)
                logger.info(f"📖 Loaded {len(self.experiences)} experiences")
        except Exception as e:
            logger.error(f"❌ Error loading: {e}")
            self.experiences = []
    
    def save_experiences(self) -> None:
        """Save all experiences."""
        try:
            data = {
                "experiences": self.experiences,
                "total_trades": self.total_trades,
                "exploration_rate": self.exploration_rate,
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.knowledge_file, 'w') as f:
                json.dump(data, f, indent=2)
            
        except Exception as e:
            logger.error(f"❌ Error saving: {e}")
    
    def get_statistics(self) -> Dict:
        """Get learning statistics."""
        if not self.experiences:
            return {
                "total_experiences": 0,
                "learning_phase": "Not started",
                "win_rate": 0,
                "avg_profit": 0
            }
        
        wins = sum(1 for exp in self.experiences if exp['outcome'].get('win', False))
        win_rate = (wins / len(self.experiences)) * 100
        
        total_pnl = sum(exp['outcome'].get('pnl', 0) for exp in self.experiences)
        avg_profit = total_pnl / len(self.experiences)
        
        # Recent performance
        recent = self.experiences[-50:] if len(self.experiences) > 50 else self.experiences
        recent_wins = sum(1 for exp in recent if exp['outcome'].get('win', False))
        recent_wr = (recent_wins / len(recent)) * 100 if recent else 0
        recent_pnl = sum(exp['outcome'].get('pnl', 0) for exp in recent)
        
        return {
            "total_experiences": len(self.experiences),
            "total_trades": self.total_trades,
            "exploration_rate": f"{self.exploration_rate:.1%}",
            "win_rate": round(win_rate, 1),
            "avg_profit": round(avg_profit, 2),
            "total_profit": round(total_pnl, 2),
            "recent_win_rate": round(recent_wr, 1),
            "recent_profit": round(recent_pnl, 2),
            "losing_streak": self.losing_streak,
            "winning_streak": self.winning_streak
        }
    
    # ========== LEGACY COMPATIBILITY ==========
    
    def should_take_trade(self, setup_details: Dict) -> Tuple[bool, str, float]:
        """Legacy compatibility."""
        market_state = self.capture_market_state(
            rsi=setup_details.get('rsi', 50),
            vwap_distance=setup_details.get('vwap_distance', 0),
            market_condition=setup_details.get('market_state', 'unknown'),
            volume_ratio=setup_details.get('volume_ratio', 1.0),
            trend=setup_details.get('trend', 'none'),
            hour=datetime.now().hour,
            minute=datetime.now().minute,
            day_of_week=datetime.now().weekday()
        )
        
        action = self.decide_action(market_state)
        
        decision = action.get('take_trade', False)
        reason = action.get('decision_type', 'reinforcement_learning')
        confidence = 1.0 - self.exploration_rate  # Less exploration = more confidence
        
        return decision, reason, confidence
    
    def record_setup_and_outcome(self, setup_details: Dict, took_trade: bool, outcome: Optional[Dict] = None) -> None:
        """Legacy compatibility."""
        if took_trade and outcome:
            market_state = self.capture_market_state(
                rsi=setup_details.get('rsi', 50),
                vwap_distance=setup_details.get('vwap_distance', 0),
                market_condition=setup_details.get('market_state', 'unknown'),
                volume_ratio=setup_details.get('volume_ratio', 1.0),
                trend=setup_details.get('trend', 'none'),
                hour=datetime.now().hour,
                minute=datetime.now().minute,
                day_of_week=datetime.now().weekday()
            )
            
            action = {
                "direction": setup_details.get('signal_type', 'unknown'),
                "stop_distance_ticks": outcome.get('stop_distance_ticks', 11),
                "target_distance_ticks": outcome.get('target_distance_ticks', 22),
                "risk_per_trade": setup_details.get('risk_per_trade', 0.012)
            }
            
            self.record_experience(market_state, action, outcome)
    
    def load_knowledge(self) -> None:
        """Legacy compatibility."""
        self.load_experiences()
    
    def save_knowledge(self) -> None:
        """Legacy compatibility."""
        self.save_experiences()
    
    def get_learned_params(self) -> Dict:
        """Return defaults for compatibility."""
        return {
            "rsi_oversold": 30,
            "rsi_overbought": 78,
            "vwap_entry_distance": 2.0,
            "risk_per_trade": 0.012,
            "stop_distance_ticks": 11,
            "stop_buffer_ticks": 2,
            "profit_target_multiplier": 2.0,
            "breakeven_threshold_ticks": 8,
            "breakeven_offset_ticks": 1,
            "trailing_stop_distance_ticks": 8,
            "trailing_min_profit_ticks": 12,
            "time_decay_50_tightening": 0.10,
            "time_decay_75_tightening": 0.20,
            "time_decay_90_tightening": 0.30,
            "partial_exit_1_r_multiple": 2.0,
            "partial_exit_1_percentage": 0.50,
            "partial_exit_2_r_multiple": 3.0,
            "partial_exit_2_percentage": 0.30,
            "partial_exit_3_r_multiple": 5.0,
            "use_time_tightening": False,
            "tightening_hour": 15,
            "tightening_ratio": 1.0,
            "max_hold_time_minutes": 240
        }
