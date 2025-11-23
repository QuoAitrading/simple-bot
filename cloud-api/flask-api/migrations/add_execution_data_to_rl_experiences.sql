-- PostgreSQL Migration: Add Execution Data to RL Experiences
-- Adds execution quality metrics for better RL learning from live trading
-- Run this on quotrading-db.postgres.database.azure.com

-- Add execution data columns to rl_experiences table
-- These columns help RL learn from execution quality, not just P&L

ALTER TABLE rl_experiences 
ADD COLUMN IF NOT EXISTS order_type_used VARCHAR(20),  -- 'passive', 'aggressive', 'mixed'
ADD COLUMN IF NOT EXISTS entry_slippage_ticks DECIMAL(10,2),  -- Actual slippage in ticks
ADD COLUMN IF NOT EXISTS partial_fill BOOLEAN DEFAULT FALSE,  -- Whether partial fill occurred
ADD COLUMN IF NOT EXISTS fill_ratio DECIMAL(3,2),  -- Percentage filled (0.00-1.00, e.g., 0.66 = 2 of 3)
ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(50),  -- 'target_reached', 'stop_loss', 'timeout', etc.
ADD COLUMN IF NOT EXISTS held_full_duration BOOLEAN DEFAULT TRUE;  -- Whether hit target/stop vs time exit

-- Create index for execution quality queries
CREATE INDEX IF NOT EXISTS idx_rl_experiences_execution ON rl_experiences(
    exit_reason, order_type_used
);

-- Add comment explaining execution data
COMMENT ON COLUMN rl_experiences.order_type_used IS 'Order type used for entry: passive (limit), aggressive (market), or mixed';
COMMENT ON COLUMN rl_experiences.entry_slippage_ticks IS 'Actual slippage in ticks from expected entry price';
COMMENT ON COLUMN rl_experiences.partial_fill IS 'True if order was only partially filled';
COMMENT ON COLUMN rl_experiences.fill_ratio IS 'Ratio of filled contracts to requested (1.0 = fully filled)';
COMMENT ON COLUMN rl_experiences.exit_reason IS 'How trade closed: target_reached, stop_loss, timeout, tightened_target, underwater_timeout, friday_profit_protection, etc.';
COMMENT ON COLUMN rl_experiences.held_full_duration IS 'True if trade hit target/stop, False if exited early due to time/conditions';

-- Example query to find trades with high slippage
-- SELECT symbol, AVG(entry_slippage_ticks) as avg_slippage, COUNT(*) as trades
-- FROM rl_experiences
-- WHERE entry_slippage_ticks > 2.0
-- GROUP BY symbol
-- ORDER BY avg_slippage DESC;

-- Example query to find exit reasons distribution
-- SELECT exit_reason, COUNT(*) as count, AVG(pnl) as avg_pnl
-- FROM rl_experiences
-- WHERE took_trade = TRUE
-- GROUP BY exit_reason
-- ORDER BY count DESC;
