"""
Volume metrics API endpoints.
"""
from datetime import date, timedelta
from fastapi import APIRouter, Query
from typing import Optional

from app.database import execute_query
from app.models import (
    FaxVolumeByDate,
    FaxVolumeResponse,
    CategoryDistribution,
    CategoryDistributionResponse,
    PagesStatsResponse,
    TimeOfDayDocument,
    TimeOfDayVolumeResponse,
)

router = APIRouter()


def get_date_filter_sql(start_date: date, end_date: date, date_column: str = "document_created_at") -> str:
    """Generate SQL for date filtering."""
    return f"{date_column} >= '{start_date}' AND {date_column} < '{end_date + timedelta(days=1)}'"


def get_ai_filter_sql(ai_intake_only: bool, table_alias: str = "") -> str:
    """Generate SQL for AI intake filtering."""
    prefix = f"{table_alias}." if table_alias else ""
    if ai_intake_only:
        return f"{prefix}is_ai_intake_enabled = true"
    return ""


@router.get("/faxes", response_model=FaxVolumeResponse)
async def get_fax_volume(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    supplier_id: Optional[str] = Query(None, description="Filter by specific supplier"),
    supplier_organization_id: Optional[str] = Query(None, description="Filter by supplier organization"),
    period: str = Query("day", description="Aggregation period: day, week, or month"),
):
    """Get total faxes received by day/week/month."""
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Determine date truncation based on period
    if period == "week":
        date_trunc = "DATE_TRUNC('week', document_created_at)"
    elif period == "month":
        date_trunc = "DATE_TRUNC('month', document_created_at)"
    else:
        date_trunc = "DATE_TRUNC('day', document_created_at)"
    
    # Build WHERE clauses
    where_clauses = [get_date_filter_sql(start_date, end_date)]
    
    if ai_intake_only:
        where_clauses.append("is_ai_intake_enabled = true")
    
    if supplier_id:
        where_clauses.append(f"supplier_id = '{supplier_id}'")
    
    if supplier_organization_id:
        where_clauses.append(f"supplier_organization_id = '{supplier_organization_id}'")
    
    where_sql = " AND ".join(where_clauses)
    
    # Add incomplete week filter for weekly aggregation
    incomplete_week_filter = ""
    if period == "week":
        incomplete_week_filter = f"AND {date_trunc}::date < DATE_TRUNC('week', CURRENT_DATE)"
    
    query = f"""
        SELECT 
            {date_trunc}::date as date,
            supplier_id,
            COUNT(*) as count
        FROM analytics.intake_documents
        WHERE {where_sql}
          {incomplete_week_filter}
        GROUP BY 1, 2
        ORDER BY 1, 2
    """
    
    results = execute_query(query)
    
    volume_data = [
        FaxVolumeByDate(date=row["date"], count=row["count"], supplier_id=row.get("supplier_id"))
        for row in results
    ]
    
    total = sum(item.count for item in volume_data)
    
    return FaxVolumeResponse(
        data=volume_data,
        total=total,
        period=period
    )


@router.get("/pages", response_model=PagesStatsResponse)
async def get_pages_stats(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    supplier_id: Optional[str] = Query(None, description="Filter by specific supplier"),
    supplier_organization_id: Optional[str] = Query(None, description="Filter by supplier organization"),
):
    """Get average pages per fax statistics."""
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Build WHERE clauses
    where_clauses = [get_date_filter_sql(start_date, end_date, "id.document_created_at")]
    
    if ai_intake_only:
        where_clauses.append("id.is_ai_intake_enabled = true")
    
    if supplier_id:
        where_clauses.append(f"id.supplier_id = '{supplier_id}'")
    
    if supplier_organization_id:
        where_clauses.append(f"id.supplier_organization_id = '{supplier_organization_id}'")
    
    where_sql = " AND ".join(where_clauses)
    
    # Join with workflow.documents to get page_count
    query = f"""
        SELECT 
            COUNT(DISTINCT id.intake_document_id) as total_documents,
            COALESCE(SUM(d.page_count), 0) as total_pages
        FROM analytics.intake_documents id
        LEFT JOIN workflow.documents d ON d.external_id = id.document_id
        WHERE {where_sql}
    """
    
    results = execute_query(query)
    
    return PagesStatsResponse(
        total_documents=results[0]["total_documents"] if results else 0,
        total_pages=int(results[0]["total_pages"]) if results and results[0]["total_pages"] is not None else 0,
        avg_pages_per_fax=None
    )


@router.get("/categories", response_model=CategoryDistributionResponse)
async def get_category_distribution(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    supplier_id: Optional[str] = Query(None, description="Filter by specific supplier"),
    supplier_organization_id: Optional[str] = Query(None, description="Filter by supplier organization"),
):
    """Get category distribution of documents (Documents -> Inbox State Categories -> Catalog Categories)."""
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Build WHERE clauses for intake_documents
    where_clauses = [get_date_filter_sql(start_date, end_date, "id.document_created_at")]
    if ai_intake_only:
        where_clauses.append("id.is_ai_intake_enabled = true")
    if supplier_id:
        where_clauses.append(f"id.supplier_id = '{supplier_id}'")
    if supplier_organization_id:
        where_clauses.append(f"id.supplier_organization_id = '{supplier_organization_id}'")
    where_sql = " AND ".join(where_clauses)
    
    query = f"""
        SELECT
            id.supplier_id,
            COALESCE(cat.name, 'Uncategorized') AS category,
            COUNT(DISTINCT id.intake_document_id) AS count
        FROM analytics.intake_documents id
        LEFT JOIN workflow.csr_inbox_states s ON id.intake_document_id = s.external_id
        LEFT JOIN workflow.csr_inbox_state_categories state_cat ON s.id = state_cat.csr_inbox_state_id
        LEFT JOIN workflow.catalog_categories cat ON state_cat.catalog_category_id = cat.id
        WHERE {where_sql}
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC
    """
    
    results = execute_query(query)
    
    total = sum(row["count"] for row in results)
    
    categories = [
        CategoryDistribution(
            category=row["category"],
            count=row["count"],
            percentage=round((row["count"] / total * 100) if total > 0 else 0, 2),
            supplier_id=row.get("supplier_id")
        )
        for row in results
    ]
    
    return CategoryDistributionResponse(
        data=categories,
        total=total
    )


@router.get("/time-of-day", response_model=TimeOfDayVolumeResponse)
async def get_time_of_day_volume(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    supplier_id: Optional[str] = Query(None, description="Filter by specific supplier"),
    supplier_organization_id: Optional[str] = Query(None, description="Filter by supplier organization"),
):
    """
    Get fax volume by hour of day (0-23).
    Aggregates across all dates in the selected range to show typical daily pattern.
    """
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Build WHERE clauses
    where_clauses = [get_date_filter_sql(start_date, end_date)]
    
    if ai_intake_only:
        where_clauses.append("is_ai_intake_enabled = true")
    
    if supplier_id:
        where_clauses.append(f"supplier_id = '{supplier_id}'")
    
    if supplier_organization_id:
        where_clauses.append(f"supplier_organization_id = '{supplier_organization_id}'")
    
    where_sql = " AND ".join(where_clauses)
    
    query = f"""
        SELECT 
            supplier_id,
            document_created_at AT TIME ZONE 'UTC' as document_created_at
        FROM analytics.intake_documents
        WHERE {where_sql}
    """
    
    results = execute_query(query)
    
    time_data = [
        TimeOfDayDocument(timestamp=row["document_created_at"], supplier_id=row.get("supplier_id"))
        for row in results
    ]
    
    total = len(time_data)
    
    return TimeOfDayVolumeResponse(
        data=time_data,
        total=total
    )
