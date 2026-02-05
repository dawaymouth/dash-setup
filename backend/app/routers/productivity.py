"""
Productivity metrics API endpoints.
"""
from datetime import date, timedelta
from fastapi import APIRouter, Query
from typing import Optional

from app.database import execute_query
from app.models import (
    IndividualProductivity,
    ProductivityResponse,
    CategoryByIndividual,
    CategoryByIndividualResponse,
)

router = APIRouter()


@router.get("/by-individual", response_model=ProductivityResponse)
async def get_productivity_by_individual(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    supplier_id: Optional[str] = Query(None, description="Filter by specific supplier"),
    supplier_organization_id: Optional[str] = Query(None, description="Filter by supplier organization"),
    limit: int = Query(50, description="Maximum number of individuals to return"),
):
    """
    Get total faxes processed by individual.
    
    Uses the last user to access each document as a proxy for who completed the
    terminal action (push, assign, email, etc.). This provides much better coverage
    than the assignee_user_id field which is often null.
    """
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    days_in_range = (end_date - start_date).days + 1
    
    # Build WHERE clauses for intake_documents (aliased as 'd')
    where_clauses = [
        f"d.document_created_at >= '{start_date}'",
        f"d.document_created_at < '{end_date + timedelta(days=1)}'",
        "d.state IN ('pushed', 'assigned', 'emailed')",  # Completed states
    ]
    
    if ai_intake_only:
        where_clauses.append("d.is_ai_intake_enabled = true")
    
    if supplier_id:
        where_clauses.append(f"d.supplier_id = '{supplier_id}'")
    
    if supplier_organization_id:
        where_clauses.append(f"d.supplier_organization_id = '{supplier_organization_id}'")
    
    where_sql = " AND ".join(where_clauses)
    
    # Query using last accessor from workflow.csr_inbox_state_accesses
    # This captures who actually completed the document action
    # Also includes median processing time for complete user processing cycles
    query = f"""
        WITH last_access AS (
            SELECT 
                a.csr_inbox_state_id,
                a.user_id,
                u.external_id as user_external_id,
                u.first_name || ' ' || u.last_name as user_name,
                ROW_NUMBER() OVER (PARTITION BY a.csr_inbox_state_id ORDER BY a.last_accessed_at DESC) as rn
            FROM workflow.csr_inbox_state_accesses a
            JOIN workflow.users u ON a.user_id = u.id
        ),
        user_processing_times AS (
            SELECT 
                la.user_external_id,
                la.user_name,
                CASE 
                    WHEN first_acc.user_id = last_acc.user_id 
                         AND first_acc.user_id IS NOT NULL
                         AND DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) > 0
                         AND DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) < 1440
                    THEN DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at)
                    ELSE NULL
                END as processing_minutes
            FROM analytics.intake_documents d
            JOIN workflow.csr_inbox_states s ON d.intake_document_id = s.external_id
            JOIN last_access la ON s.id = la.csr_inbox_state_id AND la.rn = 1
            LEFT JOIN (
                SELECT csr_inbox_state_id, user_id, created_at,
                       ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY created_at ASC) as rn
                FROM workflow.csr_inbox_state_accesses
            ) first_acc ON s.id = first_acc.csr_inbox_state_id AND first_acc.rn = 1
            LEFT JOIN (
                SELECT csr_inbox_state_id, user_id, last_accessed_at,
                       ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY last_accessed_at DESC) as rn
                FROM workflow.csr_inbox_state_accesses
            ) last_acc ON s.id = last_acc.csr_inbox_state_id AND last_acc.rn = 1
            WHERE {where_sql}
        )
        SELECT 
            user_external_id as user_id,
            user_name,
            COUNT(*) as total_processed,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY processing_minutes) as median_minutes
        FROM user_processing_times
        GROUP BY 1, 2
        ORDER BY 3 DESC
        LIMIT {limit}
    """
    
    results = execute_query(query)
    
    individuals = [
        IndividualProductivity(
            user_id=row["user_id"],
            user_name=row["user_name"] or "Unknown",
            total_processed=row["total_processed"],
            avg_per_day=round(row["total_processed"] / days_in_range, 2),
            median_minutes=round(float(row["median_minutes"]), 1) if row.get("median_minutes") else None
        )
        for row in results
    ]
    
    total_processed = sum(ind.total_processed for ind in individuals)
    
    return ProductivityResponse(
        data=individuals,
        total_processed=total_processed,
        unique_individuals=len(individuals)
    )


@router.get("/daily-average", response_model=ProductivityResponse)
async def get_daily_average_productivity(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    supplier_id: Optional[str] = Query(None, description="Filter by specific supplier"),
    supplier_organization_id: Optional[str] = Query(None, description="Filter by supplier organization"),
    limit: int = Query(50, description="Maximum number of individuals to return"),
):
    """
    Get average faxes processed per day by individual.
    
    Uses the last user to access each document as a proxy for who completed the
    terminal action. Calculates average based on active working days only.
    """
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Build WHERE clauses for intake_documents (aliased as 'd')
    where_clauses = [
        f"d.document_created_at >= '{start_date}'",
        f"d.document_created_at < '{end_date + timedelta(days=1)}'",
        "d.state IN ('pushed', 'assigned', 'emailed')",
    ]
    
    if ai_intake_only:
        where_clauses.append("d.is_ai_intake_enabled = true")
    
    if supplier_id:
        where_clauses.append(f"d.supplier_id = '{supplier_id}'")
    
    if supplier_organization_id:
        where_clauses.append(f"d.supplier_organization_id = '{supplier_organization_id}'")
    
    where_sql = " AND ".join(where_clauses)
    
    # Calculate average per active day for each individual using last accessor
    # Also includes median processing time for complete visibility
    query = f"""
        WITH last_access AS (
            SELECT 
                a.csr_inbox_state_id,
                a.user_id,
                u.external_id as user_external_id,
                u.first_name || ' ' || u.last_name as user_name,
                ROW_NUMBER() OVER (PARTITION BY a.csr_inbox_state_id ORDER BY a.last_accessed_at DESC) as rn
            FROM workflow.csr_inbox_state_accesses a
            JOIN workflow.users u ON a.user_id = u.id
        ),
        user_docs_with_times AS (
            SELECT 
                la.user_external_id,
                la.user_name,
                d.document_created_at,
                CASE 
                    WHEN first_acc.user_id = last_acc.user_id 
                         AND first_acc.user_id IS NOT NULL
                         AND DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) > 0
                         AND DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) < 1440
                    THEN DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at)
                    ELSE NULL
                END as processing_minutes
            FROM analytics.intake_documents d
            JOIN workflow.csr_inbox_states s ON d.intake_document_id = s.external_id
            JOIN last_access la ON s.id = la.csr_inbox_state_id AND la.rn = 1
            LEFT JOIN (
                SELECT csr_inbox_state_id, user_id, created_at,
                       ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY created_at ASC) as rn
                FROM workflow.csr_inbox_state_accesses
            ) first_acc ON s.id = first_acc.csr_inbox_state_id AND first_acc.rn = 1
            LEFT JOIN (
                SELECT csr_inbox_state_id, user_id, last_accessed_at,
                       ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY last_accessed_at DESC) as rn
                FROM workflow.csr_inbox_state_accesses
            ) last_acc ON s.id = last_acc.csr_inbox_state_id AND last_acc.rn = 1
            WHERE {where_sql}
        ),
        daily_counts AS (
            SELECT 
                user_external_id as user_id,
                user_name,
                DATE_TRUNC('day', document_created_at)::date as work_date,
                COUNT(*) as daily_count,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY processing_minutes) as daily_median_minutes
            FROM user_docs_with_times
            GROUP BY 1, 2, 3
        )
        SELECT 
            user_id,
            user_name,
            SUM(daily_count) as total_processed,
            AVG(daily_count) as avg_per_day,
            COUNT(DISTINCT work_date) as active_days,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY daily_median_minutes) as median_minutes
        FROM daily_counts
        GROUP BY 1, 2
        ORDER BY avg_per_day DESC
        LIMIT {limit}
    """
    
    results = execute_query(query)
    
    individuals = [
        IndividualProductivity(
            user_id=row["user_id"],
            user_name=row["user_name"] or "Unknown",
            total_processed=row["total_processed"],
            avg_per_day=round(float(row["avg_per_day"]), 2) if row["avg_per_day"] else 0,
            median_minutes=round(float(row["median_minutes"]), 1) if row.get("median_minutes") else None
        )
        for row in results
    ]
    
    total_processed = sum(ind.total_processed for ind in individuals)
    
    return ProductivityResponse(
        data=individuals,
        total_processed=total_processed,
        unique_individuals=len(individuals)
    )


@router.get("/category-breakdown", response_model=CategoryByIndividualResponse)
async def get_category_by_individual(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    supplier_id: Optional[str] = Query(None, description="Filter by specific supplier"),
    supplier_organization_id: Optional[str] = Query(None, description="Filter by supplier organization"),
    limit: int = Query(20, description="Maximum number of individuals to return"),
):
    """
    Get category percentage breakdown by individual.
    Processing times vary by category, so this helps identify specialization.
    """
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Build WHERE clauses
    where_clauses = [
        f"o.created_at >= '{start_date}'",
        f"o.created_at < '{end_date + timedelta(days=1)}'",
        "o.assignee_id IS NOT NULL",
    ]
    
    if ai_intake_only:
        where_clauses.append("s.ai_intake_enabled = true")
    
    if supplier_id:
        where_clauses.append(f"o.supplier_id = '{supplier_id}'")
    
    if supplier_organization_id:
        where_clauses.append(f"o.supplier_organization_id = '{supplier_organization_id}'")
    
    where_sql = " AND ".join(where_clauses)
    
    query = f"""
        WITH individual_totals AS (
            SELECT 
                o.assignee_id as user_id,
                o.assignee as user_name,
                COUNT(*) as total_orders
            FROM analytics.orders o
            LEFT JOIN interim.suppliers s ON o.supplier_id = s.external_id
            WHERE {where_sql}
            GROUP BY 1, 2
            ORDER BY 3 DESC
            LIMIT {limit}
        ),
        category_counts AS (
            SELECT 
                o.assignee_id as user_id,
                o.assignee as user_name,
                COALESCE(os.category, 'Uncategorized') as category,
                COUNT(DISTINCT o.order_id) as count
            FROM analytics.orders o
            LEFT JOIN analytics.order_skus os ON o.order_id = os.order_id
            LEFT JOIN interim.suppliers s ON o.supplier_id = s.external_id
            WHERE {where_sql}
              AND o.assignee_id IN (SELECT user_id FROM individual_totals)
            GROUP BY 1, 2, 3
        )
        SELECT 
            cc.user_id,
            cc.user_name,
            cc.category,
            cc.count,
            ROUND(cc.count * 100.0 / it.total_orders, 2) as percentage
        FROM category_counts cc
        JOIN individual_totals it ON cc.user_id = it.user_id
        ORDER BY cc.user_name, cc.count DESC
    """
    
    results = execute_query(query)
    
    categories = [
        CategoryByIndividual(
            user_id=row["user_id"],
            user_name=row["user_name"] or "Unknown",
            category=row["category"],
            count=row["count"],
            percentage=float(row["percentage"]) if row["percentage"] else 0
        )
        for row in results
    ]
    
    return CategoryByIndividualResponse(data=categories)


@router.get("/by-individual-processing-time", response_model=ProductivityResponse)
async def get_processing_time_by_individual(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    supplier_id: Optional[str] = Query(None, description="Filter by specific supplier"),
    supplier_organization_id: Optional[str] = Query(None, description="Filter by supplier organization"),
    limit: int = Query(50, description="Maximum number of individuals to return"),
):
    """
    Get median processing time per user for documents where they did both
    the first access and last action. Shows individual processing efficiency.
    """
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    days_in_range = (end_date - start_date).days + 1
    
    # Build WHERE clauses
    where_clauses = [
        f"d.document_created_at >= '{start_date}'",
        f"d.document_created_at < '{end_date + timedelta(days=1)}'",
        "d.state NOT IN ('new')",
    ]
    
    if ai_intake_only:
        where_clauses.append("d.is_ai_intake_enabled = true")
    
    if supplier_id:
        where_clauses.append(f"d.supplier_id = '{supplier_id}'")
    
    if supplier_organization_id:
        where_clauses.append(f"d.supplier_organization_id = '{supplier_organization_id}'")
    
    where_sql = " AND ".join(where_clauses)
    
    # Query for users who did both first and last access
    query = f"""
        WITH same_user_docs AS (
            SELECT 
                d.intake_document_id,
                first_acc.user_id,
                u.external_id as user_external_id,
                u.first_name || ' ' || u.last_name as user_name,
                DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) as processing_minutes
            FROM analytics.intake_documents d
            JOIN workflow.csr_inbox_states s ON d.intake_document_id = s.external_id
            LEFT JOIN (
                SELECT csr_inbox_state_id, user_id, created_at,
                       ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY created_at ASC) as rn
                FROM workflow.csr_inbox_state_accesses
            ) first_acc ON s.id = first_acc.csr_inbox_state_id AND first_acc.rn = 1
            LEFT JOIN (
                SELECT csr_inbox_state_id, user_id, last_accessed_at,
                       ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY last_accessed_at DESC) as rn
                FROM workflow.csr_inbox_state_accesses
            ) last_acc ON s.id = last_acc.csr_inbox_state_id AND last_acc.rn = 1
            LEFT JOIN workflow.users u ON first_acc.user_id = u.id
            WHERE {where_sql}
              AND first_acc.user_id = last_acc.user_id
              AND first_acc.user_id IS NOT NULL
              AND processing_minutes > 0
              AND processing_minutes < 1440
        )
        SELECT 
            user_external_id as user_id,
            user_name,
            COUNT(*) as total_processed,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY processing_minutes) as median_minutes
        FROM same_user_docs
        GROUP BY 1, 2
        HAVING COUNT(*) >= 5
        ORDER BY 4 ASC
        LIMIT {limit}
    """
    
    results = execute_query(query)
    
    productivity = [
        IndividualProductivity(
            user_id=row["user_id"],
            user_name=row["user_name"],
            total_processed=row["total_processed"],
            avg_per_day=round(row["total_processed"] / days_in_range, 1),
            median_minutes=round(float(row["median_minutes"]), 1) if row.get("median_minutes") else None
        )
        for row in results
    ]
    
    total_processed = sum(p.total_processed for p in productivity)
    
    return ProductivityResponse(
        data=productivity,
        total_processed=total_processed,
        unique_individuals=len(productivity)
    )
