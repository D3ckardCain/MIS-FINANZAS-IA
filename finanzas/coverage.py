"""Cobertura documental y continuidad: no completa huecos ni agrega movimientos."""
from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class CoverageReview:
    unique_documents: tuple[str, ...]
    duplicate_documents: tuple[str, ...]
    missing_ranges: tuple[tuple, ...]
    continuity_checked: int
    issues: tuple[str, ...]


def review_coverage(previews):
    previews = tuple(previews)
    accounts = {p.account_fingerprint for p in previews}
    if previews and (None in accounts or len(accounts) != 1):
        raise ValueError("La continuidad requiere documentos de una misma cuenta identificada")
    unique, duplicates, issues = {}, [], []
    for p in previews:
        if p.document_id in unique:
            previous = unique[p.document_id]
            if (p.period_start, p.period_end, p.summary) != (previous.period_start, previous.period_end, previous.summary):
                raise ValueError("Huella documental repetida con metadatos incompatibles")
            duplicates.append(p.document_id)
        else:
            unique[p.document_id] = p
    ordered = sorted(unique.values(), key=lambda p: (p.period_start, p.period_end))
    gaps = []
    checked = 0
    frontier = ordered[0].period_end if ordered else None
    for a, b in zip(ordered, ordered[1:]):
        next_day = frontier + timedelta(days=1)
        if b.period_start < next_day:
            issues.append("Períodos solapados o versiones distintas del mismo período; revisar")
        elif b.period_start > next_day:
            gaps.append((next_day, b.period_start - timedelta(days=1)))
        elif a.period_end == frontier:
            if a.summary.final is None or b.summary.initial is None:
                issues.append("Continuidad de saldos no verificable: saldo no informado")
            else:
                checked += 1
                if a.summary.final != b.summary.initial:
                    issues.append("Saldo de cierre y apertura consecutivos no coincide")
        frontier = max(frontier, b.period_end)
    return CoverageReview(tuple(p.document_id for p in ordered), tuple(duplicates),
                          tuple(gaps), checked, tuple(issues))
