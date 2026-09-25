"""Canonical semantic concepts; provider taxonomy mapping must be explicit, never guessed."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class FundamentalConcept:
    name: str
    kind: Literal["flow", "instant"]
    unit: str


FUNDAMENTAL_CONCEPTS = tuple(
    FundamentalConcept(name, "flow", "USD/share" if name == "diluted_eps" else "USD")
    for name in ("common_net_income", "net_income", "revenue", "operating_income",
                 "operating_cash_flow", "capital_expenditures", "gross_profit", "diluted_eps")
) + tuple(FundamentalConcept(name, "instant", "shares" if name == "shares_outstanding" else "USD")
          for name in ("common_equity", "assets", "total_debt", "current_debt", "long_term_debt",
                       "shares_outstanding"))
CONCEPTS = {concept.name: concept for concept in FUNDAMENTAL_CONCEPTS}
