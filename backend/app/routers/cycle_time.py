"""
Cycle time metrics API endpoints.
"""
import logging
from datetime import date, timedelta
from fastapi import APIRouter, Query
from typing import Optional

logger = logging.getLogger(__name__)

from app.cycle_time_sql import (
    build_received_to_open_business_hours_query,
    build_received_to_open_business_hours_overall_query,
)
from app.database import execute_query
from app.models import CycleTimeByDate, CycleTimeResponse, StateDistributionItem, StateDistributionResponse

router = APIRouter()


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
        query = build_received_to_open_business_hours_query(where_sql)
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
        overall_query = build_received_to_open_business_hours_overall_query(where_sql)
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
    "assigned_other": "Assigned (other)",
    "attached_to_existing": "Attached to existing order",
    "discarded": "Discarded",
    "emailed": "Emailed",
    "generated_new": "Generated new order",
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
    assignee_id: Optional[str] = Query(None, description="Filter to documents completed by this user (last accessor)"),
):
    """
    Get distribution of documents across terminal states.
    
    The 'split' and 'splitting' states are combined into a single 'Split' category.
    'Assigned' is split into Attached to existing order, Generated new order, and Assigned (other)
    using is_document_attached_to_existing_dme_order and is_document_generated_new_dme_order.
    Returns count and percentage for each state.
    When assignee_id is set, only documents whose last accessor (workflow) is that user are included.
    """
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Build WHERE clauses (for intake_documents columns)
    where_clauses = [
        f"d.document_created_at >= '{start_date}'",
        f"d.document_created_at < '{end_date + timedelta(days=1)}'",
        f"d.state IN ({','.join(repr(s) for s in INCLUDED_STATES)})",
    ]
    
    if ai_intake_only:
        where_clauses.append("d.is_ai_intake_enabled = true")
    
    if supplier_id:
        where_clauses.append(f"d.supplier_id = '{supplier_id}'")
    
    if supplier_organization_id:
        where_clauses.append(f"d.supplier_organization_id = '{supplier_organization_id}'")
    
    where_sql = " AND ".join(where_clauses)
    
    derived_state_sql = """
        CASE
            WHEN state = 'assigned' AND is_document_attached_to_existing_dme_order = true THEN 'attached_to_existing'
            WHEN state = 'assigned' AND is_document_generated_new_dme_order = true THEN 'generated_new'
            WHEN state = 'assigned' THEN 'assigned_other'
            WHEN state IN ('split', 'splitting') THEN 'split'
            ELSE state
        END
    """
    derived_state_sql_fallback = "CASE WHEN state IN ('split', 'splitting') THEN 'split' ELSE state END"

    if assignee_id:
        # Restrict to documents where the last accessor (workflow) is this user.
        # Narrow last_access to states this user has accessed (reduces window scope).
        query = f"""
            WITH states_for_user AS (
                SELECT DISTINCT a.csr_inbox_state_id
                FROM workflow.csr_inbox_state_accesses a
                JOIN workflow.users u ON a.user_id = u.id
                WHERE u.external_id = '{assignee_id}'
            ),
            last_access AS (
                SELECT
                    a.csr_inbox_state_id,
                    u.external_id AS user_external_id,
                    ROW_NUMBER() OVER (PARTITION BY a.csr_inbox_state_id ORDER BY a.last_accessed_at DESC) AS rn
                FROM workflow.csr_inbox_state_accesses a
                JOIN workflow.users u ON a.user_id = u.id
                WHERE a.csr_inbox_state_id IN (SELECT csr_inbox_state_id FROM states_for_user)
            ),
            doc_user AS (
                SELECT
                    d.state,
                    d.supplier_id,
                    d.is_document_attached_to_existing_dme_order,
                    d.is_document_generated_new_dme_order
                FROM analytics.intake_documents d
                JOIN workflow.csr_inbox_states s ON d.intake_document_id = s.external_id
                JOIN last_access la ON s.id = la.csr_inbox_state_id AND la.rn = 1
                WHERE la.user_external_id = '{assignee_id}'
                  AND {where_sql}
            )
            SELECT
                {derived_state_sql} AS state,
                supplier_id,
                COUNT(*) AS count
            FROM doc_user
            GROUP BY 1, 2
            ORDER BY 3 DESC
        """
        query_fallback_assignee = f"""
            WITH states_for_user AS (
                SELECT DISTINCT a.csr_inbox_state_id
                FROM workflow.csr_inbox_state_accesses a
                JOIN workflow.users u ON a.user_id = u.id
                WHERE u.external_id = '{assignee_id}'
            ),
            last_access AS (
                SELECT
                    a.csr_inbox_state_id,
                    u.external_id AS user_external_id,
                    ROW_NUMBER() OVER (PARTITION BY a.csr_inbox_state_id ORDER BY a.last_accessed_at DESC) AS rn
                FROM workflow.csr_inbox_state_accesses a
                JOIN workflow.users u ON a.user_id = u.id
                WHERE a.csr_inbox_state_id IN (SELECT csr_inbox_state_id FROM states_for_user)
            ),
            doc_user AS (
                SELECT d.state, d.supplier_id
                FROM analytics.intake_documents d
                JOIN workflow.csr_inbox_states s ON d.intake_document_id = s.external_id
                JOIN last_access la ON s.id = la.csr_inbox_state_id AND la.rn = 1
                WHERE la.user_external_id = '{assignee_id}'
                  AND {where_sql}
            )
            SELECT
                {derived_state_sql_fallback} AS state,
                supplier_id,
                COUNT(*) AS count
            FROM doc_user
            GROUP BY 1, 2
            ORDER BY 3 DESC
        """
    else:
        # Original: no user filter (use d. prefix only for consistency we use same where_clauses but without d. for the non-assignee path)
        base_where = " AND ".join([
            f"document_created_at >= '{start_date}'",
            f"document_created_at < '{end_date + timedelta(days=1)}'",
            f"state IN ({','.join(repr(s) for s in INCLUDED_STATES)})",
        ] + (["is_ai_intake_enabled = true"] if ai_intake_only else [])
          + ([f"supplier_id = '{supplier_id}'"] if supplier_id else [])
          + ([f"supplier_organization_id = '{supplier_organization_id}'"] if supplier_organization_id else []))
        query = f"""
            SELECT
                {derived_state_sql} AS state,
                supplier_id,
                COUNT(*) AS count
            FROM analytics.intake_documents
            WHERE {base_where}
            GROUP BY 1, 2
            ORDER BY 3 DESC
        """
        query_fallback_assignee = None

    try:
        results = execute_query(query)
    except Exception as e:
        err_msg = str(e).lower()
        if "column" in err_msg and ("does not exist" in err_msg or "not found" in err_msg):
            logger.warning(
                "State distribution: using fallback (is_document_attached_to_existing_dme_order / is_document_generated_new_dme_order not in Redshift). "
                "Document Outcomes will show a single Assigned bar until these columns exist."
            )
            query_fallback = query_fallback_assignee if assignee_id else f"""
                SELECT
                    CASE WHEN state IN ('split', 'splitting') THEN 'split' ELSE state END AS state,
                    supplier_id,
                    COUNT(*) AS count
                FROM analytics.intake_documents
                WHERE document_created_at >= '{start_date}' AND document_created_at < '{end_date + timedelta(days=1)}'
                  AND state IN ({','.join(repr(s) for s in INCLUDED_STATES)})
                  {" AND is_ai_intake_enabled = true" if ai_intake_only else ""}
                  {f" AND supplier_id = '{supplier_id}'" if supplier_id else ""}
                  {f" AND supplier_organization_id = '{supplier_organization_id}'" if supplier_organization_id else ""}
                GROUP BY 1, 2
                ORDER BY 3 DESC
            """
            results = execute_query(query_fallback)
        else:
            raise
    
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
