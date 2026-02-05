"""
Cycle time metrics API endpoints.
"""
from datetime import date, timedelta
from fastapi import APIRouter, Query
from typing import Optional

from app.database import execute_query
from app.models import CycleTimeByDate, CycleTimeResponse

router = APIRouter()


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
    Get average time from fax received to first opened.
    
    Business hours are defined as 8:00 AM - 6:00 PM, Monday-Friday.
    When exclude_non_business_hours is True, time outside these hours is not counted.
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
    
    # Calculate time difference
    # For business hours calculation, we use a simplified approach
    # that calculates raw minutes and adjusts for business hours
    if exclude_non_business_hours:
        # Simplified business hours calculation
        # Assumes 10 business hours per day (8am-6pm)
        time_calc = """
            CASE 
                WHEN EXTRACT(DOW FROM document_created_at) IN (0, 6) THEN
                    -- Weekend: count from next Monday 8am
                    DATEDIFF(minute, 
                        DATE_TRUNC('week', document_created_at + INTERVAL '7 days') + INTERVAL '8 hours',
                        document_first_accessed_at)
                WHEN EXTRACT(HOUR FROM document_created_at) < 8 THEN
                    -- Before business hours: count from 8am same day
                    DATEDIFF(minute,
                        DATE_TRUNC('day', document_created_at) + INTERVAL '8 hours',
                        document_first_accessed_at)
                WHEN EXTRACT(HOUR FROM document_created_at) >= 18 THEN
                    -- After business hours: count from 8am next business day
                    DATEDIFF(minute,
                        DATE_TRUNC('day', document_created_at) + INTERVAL '1 day' + INTERVAL '8 hours',
                        document_first_accessed_at)
                ELSE
                    -- During business hours
                    DATEDIFF(minute, document_created_at, document_first_accessed_at)
            END
        """
    else:
        time_calc = "DATEDIFF(minute, document_created_at, document_first_accessed_at)"
    
    query = f"""
        SELECT 
            DATE_TRUNC('day', document_created_at)::date as date,
            AVG({time_calc}) as avg_minutes,
            COUNT(*) as count
        FROM analytics.intake_documents
        WHERE {where_sql}
          AND {time_calc} > 0
          AND {time_calc} < 10080  -- Exclude outliers > 1 week
        GROUP BY 1
        ORDER BY 1
    """
    
    results = execute_query(query)
    
    cycle_times = [
        CycleTimeByDate(
            date=row["date"],
            avg_minutes=round(float(row["avg_minutes"]), 2) if row["avg_minutes"] else 0,
            count=row["count"]
        )
        for row in results
    ]
    
    # Calculate overall average
    total_count = sum(ct.count for ct in cycle_times)
    overall_avg = (
        sum(ct.avg_minutes * ct.count for ct in cycle_times) / total_count
        if total_count > 0 else 0
    )
    
    return CycleTimeResponse(
        data=cycle_times,
        overall_avg_minutes=round(overall_avg, 2),
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
    
    # Calculate median processing time per day
    query = f"""
        SELECT 
            DATE_TRUNC('day', document_created_at)::date as date,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY DATEDIFF(minute, document_first_accessed_at, intake_updated_at)) as avg_minutes,
            COUNT(*) as count
        FROM analytics.intake_documents
        WHERE {where_sql}
          AND intake_updated_at > document_first_accessed_at
          AND DATEDIFF(minute, document_first_accessed_at, intake_updated_at) > 0
          AND DATEDIFF(minute, document_first_accessed_at, intake_updated_at) < 1440  -- Exclude outliers > 1 day
        GROUP BY 1
        ORDER BY 1
    """
    
    results = execute_query(query)
    
    cycle_times = [
        CycleTimeByDate(
            date=row["date"],
            avg_minutes=round(float(row["avg_minutes"]), 2) if row["avg_minutes"] else 0,
            count=row["count"]
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
