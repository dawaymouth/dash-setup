"""
Cycle time metrics API endpoints.
"""
from datetime import date, timedelta
from fastapi import APIRouter, Query
from typing import Optional

from app.database import execute_query
from app.models import CycleTimeByDate, CycleTimeResponse, StateDistributionItem, StateDistributionResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Business hours helpers (8 AM – 6 PM, Mon–Fri = 600 business minutes/day)
# ---------------------------------------------------------------------------

def _clip_start_sql() -> str:
    """SQL expression that clips document_created_at forward to the next
    business-hour boundary (Mon-Fri 8am-6pm)."""
    return """
        CASE
            -- Sunday -> next Monday 8am
            WHEN EXTRACT(DOW FROM document_created_at) = 0 THEN
                DATE_TRUNC('day', document_created_at) + INTERVAL '1 day' + INTERVAL '8 hours'
            -- Saturday -> next Monday 8am
            WHEN EXTRACT(DOW FROM document_created_at) = 6 THEN
                DATE_TRUNC('day', document_created_at) + INTERVAL '2 days' + INTERVAL '8 hours'
            -- Friday after 6pm -> next Monday 8am
            WHEN EXTRACT(DOW FROM document_created_at) = 5
                 AND EXTRACT(HOUR FROM document_created_at) >= 18 THEN
                DATE_TRUNC('day', document_created_at) + INTERVAL '3 days' + INTERVAL '8 hours'
            -- Other weekday after 6pm -> next day 8am
            WHEN EXTRACT(HOUR FROM document_created_at) >= 18 THEN
                DATE_TRUNC('day', document_created_at) + INTERVAL '1 day' + INTERVAL '8 hours'
            -- Before 8am -> same day 8am
            WHEN EXTRACT(HOUR FROM document_created_at) < 8 THEN
                DATE_TRUNC('day', document_created_at) + INTERVAL '8 hours'
            -- During business hours: keep as-is
            ELSE document_created_at
        END"""


def _clip_end_sql() -> str:
    """SQL expression that clips document_first_accessed_at backward to the
    most recent business-hour boundary (Mon-Fri 8am-6pm)."""
    return """
        CASE
            -- Sunday -> previous Friday 6pm
            WHEN EXTRACT(DOW FROM document_first_accessed_at) = 0 THEN
                DATE_TRUNC('day', document_first_accessed_at) - INTERVAL '2 days' + INTERVAL '18 hours'
            -- Saturday -> previous Friday 6pm
            WHEN EXTRACT(DOW FROM document_first_accessed_at) = 6 THEN
                DATE_TRUNC('day', document_first_accessed_at) - INTERVAL '1 day' + INTERVAL '18 hours'
            -- Monday before 8am -> previous Friday 6pm
            WHEN EXTRACT(DOW FROM document_first_accessed_at) = 1
                 AND EXTRACT(HOUR FROM document_first_accessed_at) < 8 THEN
                DATE_TRUNC('day', document_first_accessed_at) - INTERVAL '3 days' + INTERVAL '18 hours'
            -- Other weekday before 8am -> previous day 6pm
            WHEN EXTRACT(HOUR FROM document_first_accessed_at) < 8 THEN
                DATE_TRUNC('day', document_first_accessed_at) - INTERVAL '1 day' + INTERVAL '18 hours'
            -- After 6pm -> same day 6pm
            WHEN EXTRACT(HOUR FROM document_first_accessed_at) >= 18 THEN
                DATE_TRUNC('day', document_first_accessed_at) + INTERVAL '18 hours'
            -- During business hours: keep as-is
            ELSE document_first_accessed_at
        END"""


def _business_minutes_sql() -> str:
    """SQL expression that computes business minutes between the already-
    clipped biz_start and biz_end columns.

    Algorithm
    ---------
    * Same day  -> simple DATEDIFF.
    * Different days ->
        partial start day  (biz_start to 6 pm)
      + partial end day    (8 am to biz_end)
      + full weekdays between start & end dates (exclusive) × 600 min.

    The weekday-count formula uses:
        gap          = calendar days strictly between the two dates
        full_weeks   = gap / 7          (integer division)
        partial      = gap % 7
        weekend_days = GREATEST(0, LEAST(partial - 5 + DOW(start), 2))
        weekdays     = full_weeks * 5 + partial - weekend_days
    where DOW follows Redshift convention (1=Mon … 5=Fri for clipped dates).
    """
    return """
        CASE
            WHEN biz_start >= biz_end THEN 0
            WHEN biz_start::date = biz_end::date THEN
                DATEDIFF(minute, biz_start, biz_end)
            ELSE
                -- Partial start day: biz_start -> 6 pm
                DATEDIFF(minute, biz_start,
                         DATE_TRUNC('day', biz_start) + INTERVAL '18 hours')
                -- Partial end day: 8 am -> biz_end
                + DATEDIFF(minute,
                           DATE_TRUNC('day', biz_end) + INTERVAL '8 hours',
                           biz_end)
                -- Full weekdays in between × 600 minutes each
                + (CASE
                    WHEN DATEDIFF(day, biz_start::date, biz_end::date) <= 1 THEN 0
                    ELSE (
                        (DATEDIFF(day, biz_start::date, biz_end::date) - 1) / 7 * 5
                        + MOD(DATEDIFF(day, biz_start::date, biz_end::date) - 1, 7)
                        - GREATEST(0, LEAST(
                            MOD(DATEDIFF(day, biz_start::date, biz_end::date) - 1, 7)
                            - 5 + EXTRACT(DOW FROM biz_start),
                            2))
                    )
                  END) * 600
        END"""


def _build_business_hours_query(where_sql: str) -> str:
    """Grouped query: median business-minutes per day per supplier."""
    return f"""
        WITH clipped AS (
            SELECT
                document_created_at,
                document_first_accessed_at,
                supplier_id,
                {_clip_start_sql()} AS biz_start,
                {_clip_end_sql()} AS biz_end
            FROM analytics.intake_documents
            WHERE {where_sql}
        ),
        biz AS (
            SELECT
                document_created_at,
                supplier_id,
                {_business_minutes_sql()} AS biz_mins
            FROM clipped
        )
        SELECT
            DATE_TRUNC('day', document_created_at)::date AS date,
            supplier_id,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY biz_mins) AS avg_minutes,
            COUNT(*) AS count
        FROM biz
        WHERE biz_mins > 0
          AND biz_mins < 6000  -- exclude outliers > ~2 business weeks
        GROUP BY 1, 2
        ORDER BY 1, 2
    """


def _build_business_hours_overall_query(where_sql: str) -> str:
    """Scalar query: overall median business-minutes across all documents."""
    return f"""
        WITH clipped AS (
            SELECT
                document_created_at,
                document_first_accessed_at,
                {_clip_start_sql()} AS biz_start,
                {_clip_end_sql()} AS biz_end
            FROM analytics.intake_documents
            WHERE {where_sql}
        ),
        biz AS (
            SELECT
                {_business_minutes_sql()} AS biz_mins
            FROM clipped
        )
        SELECT
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY biz_mins) AS median_minutes
        FROM biz
        WHERE biz_mins > 0
          AND biz_mins < 6000
    """


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/received-to-open", response_model=CycleTimeResponse)
async def get_received_to_open_time(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    supplier_id: Optional[str] = Query(None, description="Filter by specific supplier"),
    supplier_organization_id: Optional[str] = Query(None, description="Filter by supplier organization"),
    exclude_non_business_hours: bool = Query(True, description="Exclude non-business hours from calculation"),
):
    """
    Get median time from fax received to first opened.
    
    Business hours are defined as 8:00 AM - 6:00 PM, Monday-Friday.
    When exclude_non_business_hours is True, only time within business hours
    is counted (nights and weekends are properly excluded).
    Uses median instead of average to reduce the impact of outliers.
    """
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Build WHERE clauses
    where_clauses = [
        f"document_created_at >= '{start_date}'",
        f"document_created_at < '{end_date + timedelta(days=1)}'",
        "document_first_accessed_at IS NOT NULL",
    ]
    
    if ai_intake_only:
        where_clauses.append("is_ai_intake_enabled = true")
    
    if supplier_id:
        where_clauses.append(f"supplier_id = '{supplier_id}'")
    
    if supplier_organization_id:
        where_clauses.append(f"supplier_organization_id = '{supplier_organization_id}'")
    
    where_sql = " AND ".join(where_clauses)
    
    # ---- Grouped query (per day / supplier) ----
    if exclude_non_business_hours:
        query = _build_business_hours_query(where_sql)
    else:
        time_calc = "DATEDIFF(minute, document_created_at, document_first_accessed_at)"
        query = f"""
            SELECT 
                DATE_TRUNC('day', document_created_at)::date AS date,
                supplier_id,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {time_calc}) AS avg_minutes,
                COUNT(*) AS count
            FROM analytics.intake_documents
            WHERE {where_sql}
              AND {time_calc} > 0
              AND {time_calc} < 10080  -- Exclude outliers > 1 week
            GROUP BY 1, 2
            ORDER BY 1, 2
        """
    
    results = execute_query(query)
    
    cycle_times = [
        CycleTimeByDate(
            date=row["date"],
            avg_minutes=round(float(row["avg_minutes"]), 2) if row["avg_minutes"] else 0,
            count=row["count"],
            supplier_id=row.get("supplier_id")
        )
        for row in results
    ]
    
    # ---- Overall median (across all documents, not weighted from groups) ----
    if exclude_non_business_hours:
        overall_query = _build_business_hours_overall_query(where_sql)
    else:
        time_calc = "DATEDIFF(minute, document_created_at, document_first_accessed_at)"
        overall_query = f"""
            SELECT
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {time_calc}) AS median_minutes
            FROM analytics.intake_documents
            WHERE {where_sql}
              AND {time_calc} > 0
              AND {time_calc} < 10080
        """
    
    overall_results = execute_query(overall_query)
    overall_median = (
        round(float(overall_results[0]["median_minutes"]), 2)
        if overall_results and overall_results[0]["median_minutes"] is not None
        else 0
    )
    
    return CycleTimeResponse(
        data=cycle_times,
        overall_avg_minutes=overall_median,
        metric_type="received_to_open"
    )


@router.get("/processing", response_model=CycleTimeResponse)
async def get_processing_time(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    supplier_id: Optional[str] = Query(None, description="Filter by specific supplier"),
    supplier_organization_id: Optional[str] = Query(None, description="Filter by supplier organization"),
):
    """
    Get median processing time from document open to accept/send to facility.
    Uses median instead of average to avoid skew from outliers.
    """
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Build WHERE clauses
    where_clauses = [
        f"document_created_at >= '{start_date}'",
        f"document_created_at < '{end_date + timedelta(days=1)}'",
        "document_first_accessed_at IS NOT NULL",
        "state NOT IN ('new')",  # All processed documents
    ]
    
    if ai_intake_only:
        where_clauses.append("is_ai_intake_enabled = true")
    
    if supplier_id:
        where_clauses.append(f"supplier_id = '{supplier_id}'")
    
    if supplier_organization_id:
        where_clauses.append(f"supplier_organization_id = '{supplier_organization_id}'")
    
    where_sql = " AND ".join(where_clauses)
    
    # Calculate median processing time per day per supplier
    query = f"""
        SELECT 
            DATE_TRUNC('day', document_created_at)::date as date,
            supplier_id,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY DATEDIFF(minute, document_first_accessed_at, intake_updated_at)) as avg_minutes,
            COUNT(*) as count
        FROM analytics.intake_documents
        WHERE {where_sql}
          AND intake_updated_at > document_first_accessed_at
          AND DATEDIFF(minute, document_first_accessed_at, intake_updated_at) > 0
          AND DATEDIFF(minute, document_first_accessed_at, intake_updated_at) < 1440  -- Exclude outliers > 1 day
        GROUP BY 1, 2
        ORDER BY 1, 2
    """
    
    results = execute_query(query)
    
    cycle_times = [
        CycleTimeByDate(
            date=row["date"],
            avg_minutes=round(float(row["avg_minutes"]), 2) if row["avg_minutes"] else 0,
            count=row["count"],
            supplier_id=row.get("supplier_id")
        )
        for row in results
    ]
    
    # Calculate overall median across all documents (not per-day weighted)
    overall_query = f"""
        SELECT 
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY DATEDIFF(minute, document_first_accessed_at, intake_updated_at)) as median_minutes
        FROM analytics.intake_documents
        WHERE {where_sql}
          AND intake_updated_at > document_first_accessed_at
          AND DATEDIFF(minute, document_first_accessed_at, intake_updated_at) > 0
          AND DATEDIFF(minute, document_first_accessed_at, intake_updated_at) < 1440
    """
    
    overall_results = execute_query(overall_query)
    overall_median = (
        round(float(overall_results[0]["median_minutes"]), 2) 
        if overall_results and overall_results[0]["median_minutes"] is not None 
        else 0
    )
    
    return CycleTimeResponse(
        data=cycle_times,
        overall_avg_minutes=overall_median,
        metric_type="processing"
    )


# ---------------------------------------------------------------------------
# State distribution labels
# ---------------------------------------------------------------------------

STATE_LABELS = {
    "assigned": "Assigned",
    "discarded": "Discarded",
    "emailed": "Emailed",
    "pushed": "Pushed",
    "split": "Split",
}

INCLUDED_STATES = ("assigned", "discarded", "emailed", "pushed", "split", "splitting")


@router.get("/state-distribution", response_model=StateDistributionResponse)
async def get_state_distribution(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    supplier_id: Optional[str] = Query(None, description="Filter by specific supplier"),
    supplier_organization_id: Optional[str] = Query(None, description="Filter by supplier organization"),
):
    """
    Get distribution of documents across terminal states.
    
    The 'split' and 'splitting' states are combined into a single 'Split' category.
    Returns count and percentage for each state.
    """
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Build WHERE clauses
    where_clauses = [
        f"document_created_at >= '{start_date}'",
        f"document_created_at < '{end_date + timedelta(days=1)}'",
        f"state IN ({','.join(repr(s) for s in INCLUDED_STATES)})",
    ]
    
    if ai_intake_only:
        where_clauses.append("is_ai_intake_enabled = true")
    
    if supplier_id:
        where_clauses.append(f"supplier_id = '{supplier_id}'")
    
    if supplier_organization_id:
        where_clauses.append(f"supplier_organization_id = '{supplier_organization_id}'")
    
    where_sql = " AND ".join(where_clauses)
    
    query = f"""
        SELECT
            CASE WHEN state IN ('split', 'splitting') THEN 'split' ELSE state END AS state,
            supplier_id,
            COUNT(*) AS count
        FROM analytics.intake_documents
        WHERE {where_sql}
        GROUP BY 1, 2
        ORDER BY 3 DESC
    """
    
    results = execute_query(query)
    
    # Aggregate across suppliers to get totals per state
    state_totals: dict[str, int] = {}
    state_supplier_rows: list[dict] = []
    
    for row in results:
        state = row["state"]
        count = row["count"]
        state_totals[state] = state_totals.get(state, 0) + count
        state_supplier_rows.append(row)
    
    total = sum(state_totals.values())
    
    items = [
        StateDistributionItem(
            state=state,
            label=STATE_LABELS.get(state, state.title()),
            count=count,
            percentage=round(count * 100.0 / total, 2) if total > 0 else 0,
        )
        for state, count in sorted(state_totals.items(), key=lambda x: x[1], reverse=True)
    ]
    
    return StateDistributionResponse(data=items, total=total)
