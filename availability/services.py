"""E06 reliability rules (US23).

Reports are community observations, not live connectivity checks. A report
counts for REPORT_WINDOW_DAYS. Each person gets one voice per hotspot: only
their newest report in the window is counted. The reliability score is the
share of those reports that say "Working", and it is only shown once at least
MIN_REPORTS different people have reported.
"""

from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from .models import AvailabilityReport

REPORT_WINDOW_DAYS = 30
MIN_REPORTS = 3
RECENT_REPORT_LIMIT = 5


def _current_reports(hotspot_ids):
    """Each reporter's newest in-window report per hotspot, newest first."""
    cutoff = timezone.now() - timedelta(days=REPORT_WINDOW_DAYS)
    rows = (
        AvailabilityReport.objects.filter(
            hotspot_id__in=hotspot_ids, created_at__gte=cutoff
        )
        .select_related("reporter")
        .order_by("-created_at", "-pk")
    )
    seen = set()
    current = defaultdict(list)
    for report in rows:
        key = (report.hotspot_id, report.reporter_id)
        if key not in seen:
            seen.add(key)
            current[report.hotspot_id].append(report)
    return current


def _summarize(reports):
    total = len(reports)
    working = sum(
        1 for report in reports if report.status == AvailabilityReport.Status.WORKING
    )
    has_enough = total >= MIN_REPORTS
    return {
        "score": round(100 * working / total) if has_enough else None,
        "has_enough": has_enough,
        "report_count": total,
        "working_count": working,
        "unavailable_count": total - working,
        "latest_report_at": reports[0].created_at if reports else None,
        "reports": reports[:RECENT_REPORT_LIMIT],
        "window_days": REPORT_WINDOW_DAYS,
        "min_reports": MIN_REPORTS,
    }


def hotspot_availability(hotspot):
    return _summarize(_current_reports([hotspot.pk])[hotspot.pk])


def availability_by_hotspot(hotspot_ids):
    """Summaries for many hotspots in one query; hotspots without reports map to an empty summary."""
    current = _current_reports(list(hotspot_ids))
    return {pk: _summarize(current[pk]) for pk in hotspot_ids}
