"""Avaliacao da classificacao contra o conjunto rotulado (spike 2).

Uso: python -m app.classification.evaluation [--llm] [--errors]
Sem --llm mede so as regras; com --llm exige ANTHROPIC_API_KEY e gasta chamadas reais.
"""

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.classification.domain import Context, Decision
from app.classification.llm import AnthropicClassifier, LLMClassifier
from app.classification.service import classify_message

DEFAULT_GOLDEN = Path(__file__).parent / "golden" / "contabilidade_v1.jsonl"
FIELDS = ("sector", "kind", "urgency")


@dataclass(frozen=True, slots=True)
class GoldenCase:
    id: str
    text: str
    context: Context
    expected: dict[str, str]


@dataclass(frozen=True, slots=True)
class EvalError:
    case_id: str
    text: str
    expected: dict[str, str]
    got: dict[str, str]
    source: str


@dataclass(frozen=True, slots=True)
class EvalReport:
    total: int
    source_counts: dict[str, int]
    rule_coverage: float
    rule_precision: float
    review_rate: float
    accuracy: dict[str, float]
    errors: list[EvalError]

    def render(self, *, show_errors: bool = False) -> str:
        lines = [
            f"mensagens: {self.total}",
            f"origem: {dict(self.source_counts)}",
            f"cobertura das regras: {self.rule_coverage:.0%}",
            f"precisao das regras (quando decidem): {self.rule_precision:.0%}",
            f"vao para revisao humana: {self.review_rate:.0%}",
            "acerto geral: "
            + ", ".join(f"{name}={value:.0%}" for name, value in self.accuracy.items()),
            f"erros: {len(self.errors)}",
        ]
        if show_errors:
            for error in self.errors:
                lines.append(
                    f"  [{error.case_id}] ({error.source}) {error.text!r}\n"
                    f"      esperado={error.expected} obtido={error.got}"
                )
        return "\n".join(lines)


def load_golden(path: Path = DEFAULT_GOLDEN) -> list[GoldenCase]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        context = Context(
            contact_type=raw.get("contact_type"),
            has_open_demand=raw.get("has_open_demand", False),
            has_media=raw.get("has_media", False),
        )
        cases.append(GoldenCase(raw["id"], raw["text"], context, raw["expected"]))
    return cases


def _got(decision: Decision) -> dict[str, str]:
    c = decision.classification
    return {"action": decision.action, "sector": c.sector, "kind": c.kind, "urgency": c.urgency}


def _is_exact(expected: dict[str, str], got: dict[str, str]) -> bool:
    if expected["action"] != got["action"]:
        return False
    if expected["action"] != "classified":
        return True
    return all(expected[field] == got[field] for field in FIELDS)


def evaluate(cases: list[GoldenCase], llm: LLMClassifier | None = None) -> EvalReport:
    if not cases:
        raise ValueError("conjunto rotulado vazio")
    outcomes = [(case, classify_message(case.text, case.context, llm=llm)) for case in cases]
    total = len(outcomes)
    sources = Counter(decision.classification.source for _, decision in outcomes)

    by_rule = [(c, d) for c, d in outcomes if d.classification.source == "rule"]
    rule_ok = sum(_is_exact(c.expected, _got(d)) for c, d in by_rule)
    reviews = sum(d.classification.needs_review for _, d in outcomes)

    classified_cases = [(c, d) for c, d in outcomes if c.expected["action"] == "classified"]
    accuracy = {"action": sum(c.expected["action"] == d.action for c, d in outcomes) / total}
    for field in FIELDS:
        hits = sum(c.expected[field] == _got(d)[field] for c, d in classified_cases)
        accuracy[field] = hits / len(classified_cases) if classified_cases else 0.0

    errors = [
        EvalError(c.id, c.text, c.expected, _got(d), d.classification.source)
        for c, d in outcomes
        if not _is_exact(c.expected, _got(d))
    ]
    return EvalReport(
        total=total,
        source_counts=dict(sources),
        rule_coverage=len(by_rule) / total,
        rule_precision=rule_ok / len(by_rule) if by_rule else 0.0,
        review_rate=reviews / total,
        accuracy=accuracy,
        errors=errors,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.classification.evaluation")
    parser.add_argument("--llm", action="store_true", help="usa a IA (chamadas reais, custo)")
    parser.add_argument("--errors", action="store_true", help="lista cada erro")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    llm = AnthropicClassifier() if args.llm else None
    print(evaluate(load_golden(), llm=llm).render(show_errors=args.errors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
