"""Per-turn cost + recursion guards (PRD §11.6, FR-AGT-08/10).

A `TokenBudget` accompanies every request as it flows through the agent
graph. `route_to_agent` calls `charge_hop()`; LLM calls accumulate via
`charge_tokens()`. Anything that reaches `exceeded` triggers a graceful
downgrade (per-tool try/except already returns a partial result; the
graph still terminates at the UI Agent — invariant #6).

The slice does not yet enforce hops because orchestrator → research →
ui_agent runs as a direct call. The seam exists now so subsystem 7 can
wire `route_to_agent` against it without re-plumbing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TokenBudget:
    tokens_used: int = 0
    tokens_limit: int = 60000
    hops_used: int = 0
    hops_limit: int = 4

    def charge_tokens(self, n: int) -> None:
        if n < 0:
            raise ValueError(f"token charge must be non-negative, got {n}")
        self.tokens_used += n

    def charge_hop(self) -> None:
        self.hops_used += 1

    @property
    def hops_exceeded(self) -> bool:
        return self.hops_used >= self.hops_limit

    @property
    def tokens_exceeded(self) -> bool:
        return self.tokens_used >= self.tokens_limit

    @property
    def exceeded(self) -> bool:
        return self.hops_exceeded or self.tokens_exceeded

    def remaining_tokens(self) -> int:
        return max(0, self.tokens_limit - self.tokens_used)

    def remaining_hops(self) -> int:
        return max(0, self.hops_limit - self.hops_used)
