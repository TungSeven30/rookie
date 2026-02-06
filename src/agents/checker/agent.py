"""Checker Agent implementation for Phase 5 review infrastructure."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping


@dataclass(slots=True)
class CheckerFlag:
    """Single checker finding requiring human attention."""

    code: str
    field: str
    severity: str
    message: str
    source_value: str | None = None
    prepared_value: str | None = None
    prior_year_value: str | None = None
    variance_pct: float | None = None


@dataclass(slots=True)
class CheckerReport:
    """Checker report summarizing findings for a task."""

    task_id: int
    flags: list[CheckerFlag]
    approval_blocked: bool = True
    error_detection_rate: float | None = None

    @property
    def status(self) -> str:
        """Return high-level checker status."""
        return "flagged" if self.flags else "clear"

    @property
    def flag_count(self) -> int:
        """Return number of checker flags."""
        return len(self.flags)

    def to_dict(self) -> dict[str, object]:
        """Serialize report for API responses and artifact storage."""
        return {
            "task_id": self.task_id,
            "status": self.status,
            "flag_count": self.flag_count,
            "flags": [asdict(flag) for flag in self.flags],
            "approval_blocked": self.approval_blocked,
            "error_detection_rate": self.error_detection_rate,
        }


class CheckerAgent:
    """Checker Agent for numeric verification and variance review.

    This agent intentionally never approves a task. It only returns
    structured flags for human review.
    """

    _ABS_TOLERANCE = Decimal("0.01")
    _REL_TOLERANCE = Decimal("0.001")
    _VARIANCE_THRESHOLD = Decimal("0.10")

    def run_check(
        self,
        task_id: int,
        source_values: Mapping[str, str | int | float | Decimal],
        prepared_values: Mapping[str, str | int | float | Decimal],
        prior_year_values: Mapping[str, str | int | float | Decimal] | None = None,
        documented_reasons: Mapping[str, str] | None = None,
        injected_error_fields: list[str] | None = None,
    ) -> CheckerReport:
        """Run checker analysis and produce a report."""
        flags: list[CheckerFlag] = []
        prior = prior_year_values or {}
        reasons = documented_reasons or {}

        all_fields = sorted(set(source_values) | set(prepared_values))
        for field in all_fields:
            source = self._to_decimal(source_values.get(field))
            prepared = self._to_decimal(prepared_values.get(field))
            if source is None and prepared is not None:
                flags.append(
                    CheckerFlag(
                        code="MISSING_SOURCE_VALUE",
                        field=field,
                        severity="high",
                        message="Prepared value has no matching source value.",
                        prepared_value=self._to_str(prepared),
                    )
                )
                continue
            if source is not None and prepared is None:
                flags.append(
                    CheckerFlag(
                        code="MISSING_PREPARED_VALUE",
                        field=field,
                        severity="medium",
                        message="Source value is present but prepared value is missing.",
                        source_value=self._to_str(source),
                    )
                )
                continue
            if source is None or prepared is None:
                continue

            delta = abs(source - prepared)
            tolerance = max(self._ABS_TOLERANCE, abs(source) * self._REL_TOLERANCE)
            if delta > tolerance:
                flags.append(
                    CheckerFlag(
                        code="SOURCE_MISMATCH",
                        field=field,
                        severity="high",
                        message="Prepared value does not match source document.",
                        source_value=self._to_str(source),
                        prepared_value=self._to_str(prepared),
                    )
                )

        for field, prepared_raw in prepared_values.items():
            prepared = self._to_decimal(prepared_raw)
            prior_value = self._to_decimal(prior.get(field))
            if prepared is None or prior_value is None:
                continue

            has_reason = bool(reasons.get(field, "").strip())
            if prior_value == 0:
                if prepared != 0 and not has_reason:
                    flags.append(
                        CheckerFlag(
                            code="PRIOR_YEAR_VARIANCE_NO_REASON",
                            field=field,
                            severity="medium",
                            message="Field changed from zero without documented reason.",
                            prepared_value=self._to_str(prepared),
                            prior_year_value=self._to_str(prior_value),
                            variance_pct=None,
                        )
                    )
                continue

            variance = abs((prepared - prior_value) / prior_value)
            if variance >= self._VARIANCE_THRESHOLD and not has_reason:
                flags.append(
                    CheckerFlag(
                        code="PRIOR_YEAR_VARIANCE_NO_REASON",
                        field=field,
                        severity="medium",
                        message="Significant prior-year variance without documented reason.",
                        prepared_value=self._to_str(prepared),
                        prior_year_value=self._to_str(prior_value),
                        variance_pct=float(variance),
                    )
                )

        error_detection_rate: float | None = None
        if injected_error_fields:
            injected = {field for field in injected_error_fields if field}
            if injected:
                detected = {
                    flag.field
                    for flag in flags
                    if flag.code in {"SOURCE_MISMATCH", "MISSING_SOURCE_VALUE"}
                }
                error_detection_rate = len(injected & detected) / len(injected)

        return CheckerReport(
            task_id=task_id,
            flags=flags,
            approval_blocked=True,
            error_detection_rate=error_detection_rate,
        )

    @staticmethod
    def _to_decimal(value: object) -> Decimal | None:
        """Convert numeric-like inputs to Decimal."""
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    @staticmethod
    def _to_str(value: Decimal | None) -> str | None:
        """Format decimal values as strings for JSON responses."""
        if value is None:
            return None
        return format(value, "f")

