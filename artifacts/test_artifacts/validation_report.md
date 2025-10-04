# Validation Report


## Schema Checks

- config.yaml required: PASS
- config.yaml constraints: 7/8 PASS
- .env required: PASS
- .env constraints: 2/3 PASS

## Simulators

- unit_signal_vectors:
  - strong_momentum_entry: PASS :: {"name": "strong_momentum_entry", "result": {"name": "strong_momentum_entry", "enter": true}, "expect": {"enter": true, "size_range_usd": [100, 1500]}, "pass": true}
  - ambiguous_mempool_skip: FAIL :: {"name": "ambiguous_mempool_skip", "result": {"name": "ambiguous_mempool_skip", "enter": true}, "expect": {"enter": false, "skip_reason": "ambiguous_mempool"}, "pass": false}
  - too_thin_pool_block: PASS :: {"name": "too_thin_pool_block", "result": {"name": "too_thin_pool_block", "enter": false}, "expect": {"enter": false, "skip_reason": "SE_above_max"}, "pass": true}
  - lp_add_exit: PASS :: {"name": "lp_add_exit", "result": {"name": "lp_add_exit", "exit": true}, "expect": {"exit": true, "exit_reason": "LD_positive"}, "pass": true}
  - tp_exit: PASS :: {"name": "tp_exit", "result": {"name": "tp_exit", "exit": true}, "expect": {"exit": true, "exit_reason": "TP_hit"}, "pass": true}
  - Summary: 4/5 PASS
- cadence_cases:
  - high_gas_backoff: PASS :: {"name": "high_gas_backoff", "cooldown_factor": 2.0, "expect": {"cooldown_factor_min": 2.0}, "pass": true}
  - quiet_market_backoff: PASS :: {"name": "quiet_market_backoff", "cooldown_factor": 2.0, "expect": {"cooldown_factor_min": 2.0}, "pass": true}
  - weak_signals_backoff: PASS :: {"name": "weak_signals_backoff", "cooldown_factor": 1.5, "expect": {"cooldown_factor_min": 1.5}, "pass": true}
  - block_gap_enforced: PASS :: {"name": "block_gap_enforced", "cooldown_factor": 2.0, "allow_probe": false, "expect": {"allow_probe": false}, "pass": true}
  - Summary: 4/4 PASS
- breaker_cases:
  - lp_drain_trigger: PASS :: {"name": "lp_drain_trigger", "result": {"trading": "OFF", "reason": "LP_DRAIN"}, "expect": {"trading": "OFF", "reason": "LP_DRAIN"}, "pass": true}
  - daily_gas_trigger: PASS :: {"name": "daily_gas_trigger", "result": {"probes": "OFF", "entries": "OFF"}, "expect": {"probes": "OFF", "entries": "OFF"}, "pass": true}
  - daily_loss_trigger: PASS :: {"name": "daily_loss_trigger", "result": {"trading": "OFF", "reason": "DAILY_LOSS"}, "expect": {"trading": "OFF", "reason": "DAILY_LOSS"}, "pass": true}
  - Summary: 3/3 PASS
- execution_cases:
  - slippage_guard: PASS :: {"name": "slippage_guard", "swap_allowed": true, "expect": {"swap_allowed": true}, "pass": true}
  - slippage_violation: PASS :: {"name": "slippage_violation", "swap_allowed": false, "reason": "slippage_cap", "expect": {"swap_allowed": false, "reason": "slippage_cap"}, "pass": true}
  - private_relay_policy: PASS :: {"name": "private_relay_policy", "entry_allowed": true, "expect": {"entry_allowed": true}, "pass": true}
  - Summary: 3/3 PASS