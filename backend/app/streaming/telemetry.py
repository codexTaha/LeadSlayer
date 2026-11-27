from __future__ import annotations

import time
from app.models.schemas import ModelId, RejectionCategory, SlayerVerdict, TelemetryMetrics


class TelemetryAggregator:
    """Maintains authoritative live metrics for a single pipeline run."""

    def __init__(self, total_leads: int) -> None:
        self._started_at = time.perf_counter()
        self._total_leads = total_leads
        self._processed_leads = 0
        self._killed_count = 0
        self._survived_count = 0
        self._latency_sum_ms = 0
        self._rejection_breakdown: dict[str, int] = {}
        self._model_calls: dict[str, int] = {
            ModelId.GEMINI_4_HYDROGEN.value: 0,
            ModelId.GEMINI_3_5_FLASH_LITE.value: 0,
            ModelId.GEMINI_EMBEDDING_2.value: 0,
        }
        self._verdicts_by_id: dict[str, SlayerVerdict] = {}

    def set_total_leads(self, total_leads: int) -> None:
        self._total_leads = max(0, total_leads)

    def record_model_call(self, model_id: ModelId | str) -> None:
        key = model_id.value if isinstance(model_id, ModelId) else str(model_id)
        self._model_calls[key] = self._model_calls.get(key, 0) + 1

    def record_verdict(self, verdict: SlayerVerdict) -> None:
        prev = self._verdicts_by_id.get(verdict.lead_id)
        if prev is not None:
            self._processed_leads = max(0, self._processed_leads - 1)
            self._latency_sum_ms = max(0, self._latency_sum_ms - max(0, prev.latency_ms))
            if prev.survived:
                self._survived_count = max(0, self._survived_count - 1)
            else:
                self._killed_count = max(0, self._killed_count - 1)
                if prev.rejection_category is not None:
                    cat = prev.rejection_category.value
                    cur = self._rejection_breakdown.get(cat, 0)
                    if cur <= 1:
                        self._rejection_breakdown.pop(cat, None)
                    else:
                        self._rejection_breakdown[cat] = cur - 1

        self._verdicts_by_id[verdict.lead_id] = verdict
        self._processed_leads += 1
        self._latency_sum_ms += max(0, verdict.latency_ms)
        if verdict.survived:
            self._survived_count += 1
        else:
            self._killed_count += 1
            if verdict.rejection_category is not None:
                cat = verdict.rejection_category.value
                self._rejection_breakdown[cat] = self._rejection_breakdown.get(cat, 0) + 1

    def record_resurrection(self, old_category: RejectionCategory | None) -> None:
        if self._killed_count > 0:
            self._killed_count -= 1
        self._survived_count += 1
        if old_category is not None:
            key = old_category.value
            current = self._rejection_breakdown.get(key, 0)
            if current <= 1:
                self._rejection_breakdown.pop(key, None)
            else:
                self._rejection_breakdown[key] = current - 1

    def snapshot(self) -> TelemetryMetrics:
        kill_rate = (
            round((self._killed_count / self._processed_leads) * 100.0, 1)
            if self._processed_leads > 0
            else 0.0
        )
        avg_latency = (
            round(self._latency_sum_ms / self._processed_leads, 1)
            if self._processed_leads > 0
            else 0.0
        )
        elapsed_ms = int((time.perf_counter() - self._started_at) * 1000)
        return TelemetryMetrics(
            total_leads=self._total_leads,
            processed_leads=self._processed_leads,
            killed_count=self._killed_count,
            survived_count=self._survived_count,
            kill_rate_pct=kill_rate,
            rejection_breakdown=dict(self._rejection_breakdown),
            model_calls=dict(self._model_calls),
            avg_slayer_latency_ms=avg_latency,
            elapsed_ms=elapsed_ms,
            estimated_saved_spam_hours=round(self._killed_count * 0.25, 2),
        )
