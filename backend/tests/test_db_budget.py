"""Connection budget verification test.

Verifies: DB_POOL_PROCESS_COUNT * (DB_POOL_SIZE + DB_MAX_OVERFLOW) + DB_CONNECTION_RESERVE <= DB_CONNECTION_BUDGET
Reference: F-4 (postgres-database-hardening-and-security)
"""

from novelai.config.settings import settings


def test_connection_budget_invariant() -> None:
    """Connection budget formula must hold across all processes."""
    process_count = settings.DB_POOL_PROCESS_COUNT
    pool_size = settings.DB_POOL_SIZE
    max_overflow = settings.DB_MAX_OVERFLOW
    reserve = settings.DB_CONNECTION_RESERVE
    budget = settings.DB_CONNECTION_BUDGET

    peak_connections = process_count * (pool_size + max_overflow) + reserve
    assert peak_connections <= budget, (
        f"Connection budget violated: {process_count} * ({pool_size} + {max_overflow}) "
        f"+ {reserve} = {peak_connections} > budget ({budget})"
    )
