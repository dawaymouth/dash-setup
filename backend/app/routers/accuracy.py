"""
Accuracy metrics API endpoints.

Calculates AI extraction accuracy by comparing initial system-preselected values
to final values (case-insensitive).

- Accuracy = documents where field value didn't change / total documents
- Only counts fields where the initial value was set by the system (user_id IS NULL)
- Comparison is case-insensitive using LOWER()
"""
from datetime import date, timedelta
from fastapi import APIRouter, Query
from typing import Optional

from app.database import execute_query
from app.models import (
    FieldAccuracy,
    PerFieldAccuracyResponse,
    DocumentAccuracyResponse,
    AccuracyTrendPoint,
    AccuracyTrendResponse,
)

router = APIRouter()


def build_base_ctes(start_date: date, end_date: date, supplier_filter: str = "", supplier_organization_external_id: Optional[str] = None) -> str:
    """
    Build the common CTEs for accuracy calculation.
    
    Returns CTEs that:
    1. Find first system-preselected value per document+field
    2. Find last value per document+field
    3. Compare them case-insensitively
    
    Uses workflow.suppliers for AI intake filtering (more current than interim.suppliers).
    For organization filtering, joins with workflow.supplier_organizations to map external_id to internal id.
    """
    # Determine if we need supplier joins
    needs_supplier_join = bool(supplier_filter) or supplier_organization_external_id is not None
    
    # Build the supplier join clause
    supplier_join = ""
    if needs_supplier_join:
        supplier_join = "JOIN workflow.suppliers sup ON s.supplier_id = sup.id"
        if supplier_organization_external_id:
            supplier_join += "\nJOIN workflow.supplier_organizations so ON sup.supplier_organization_id = so.id"
    
    # Build organization filter
    org_filter = ""
    if supplier_organization_external_id:
        org_filter = f" AND so.external_id = '{supplier_organization_external_id}'"
    
    return f"""
        first_values AS (
            SELECT 
                a.csr_inbox_state_id, 
                a.record_type, 
                a.field_identifier, 
                a.field_value,
                a.created_at,
                ROW_NUMBER() OVER (
                    PARTITION BY a.csr_inbox_state_id, a.field_identifier 
                    ORDER BY a.created_at ASC
                ) as rn
            FROM workflow.csr_inbox_state_data_audits a
            JOIN workflow.csr_inbox_states s ON a.csr_inbox_state_id = s.id
            {supplier_join}
            WHERE a.user_id IS NULL
              AND a.created_at >= '{start_date}'
              AND a.created_at < '{end_date + timedelta(days=1)}'
              {supplier_filter}
              {org_filter}
        ),
        last_values AS (
            SELECT 
                a.csr_inbox_state_id, 
                a.field_identifier, 
                a.field_value,
                ROW_NUMBER() OVER (
                    PARTITION BY a.csr_inbox_state_id, a.field_identifier 
                    ORDER BY a.created_at DESC
                ) as rn
            FROM workflow.csr_inbox_state_data_audits a
            JOIN workflow.csr_inbox_states s ON a.csr_inbox_state_id = s.id
            {supplier_join}
            WHERE a.created_at >= '{start_date}'
              AND a.created_at < '{end_date + timedelta(days=1)}'
              {supplier_filter}
              {org_filter}
        ),
        comparisons AS (
            SELECT 
                f.record_type, 
                f.field_identifier, 
                f.csr_inbox_state_id,
                f.created_at,
                CASE WHEN LOWER(COALESCE(f.field_value, '')) = LOWER(COALESCE(l.field_value, '')) 
                     THEN 1 ELSE 0 END as is_accurate
            FROM first_values f
            JOIN last_values l ON f.csr_inbox_state_id = l.csr_inbox_state_id 
                               AND f.field_identifier = l.field_identifier
            WHERE f.rn = 1 AND l.rn = 1
        )
    """


@router.get("/per-field", response_model=PerFieldAccuracyResponse)
async def get_per_field_accuracy(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    supplier_id: Optional[str] = Query(None, description="Filter by specific supplier"),
    supplier_organization_id: Optional[str] = Query(None, description="Filter by supplier organization"),
):
    """
    Get accuracy metrics per field type.
    
    Accuracy is calculated as: documents where initial system value matches final value
    (case-insensitive) / total documents with system-preselected values.
    
    Only includes fields where the system set the initial value (user_id IS NULL).
    """
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Build supplier filter
    supplier_filter = ""
    if ai_intake_only:
        supplier_filter += " AND sup.ai_intake_enabled = true"
    if supplier_id:
        supplier_filter += f" AND sup.external_id = '{supplier_id}'"
    
    base_ctes = build_base_ctes(start_date, end_date, supplier_filter, supplier_organization_id)
    
    query = f"""
        WITH {base_ctes}
        SELECT 
            record_type,
            field_identifier,
            COUNT(*) as total_docs,
            SUM(is_accurate) as accurate_docs,
            ROUND(100.0 * SUM(is_accurate) / NULLIF(COUNT(*), 0), 2) as accuracy_pct
        FROM comparisons
        GROUP BY 1, 2
        HAVING COUNT(*) > 100
        ORDER BY accuracy_pct ASC
    """
    
    results = execute_query(query)
    
    fields = [
        FieldAccuracy(
            record_type=row["record_type"],
            field_identifier=row["field_identifier"],
            total_docs=row["total_docs"],
            accurate_docs=row["accurate_docs"],
            accuracy_pct=float(row["accuracy_pct"]) if row["accuracy_pct"] else 0
        )
        for row in results
    ]
    
    # Calculate overall weighted accuracy
    total_docs = sum(f.total_docs for f in fields)
    total_accurate = sum(f.accurate_docs for f in fields)
    overall_accuracy = round(100.0 * total_accurate / total_docs, 2) if total_docs > 0 else 0
    
    return PerFieldAccuracyResponse(
        data=fields,
        overall_accuracy_pct=overall_accuracy,
        total_fields=len(fields)
    )


@router.get("/document-level", response_model=DocumentAccuracyResponse)
async def get_document_accuracy(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    supplier_id: Optional[str] = Query(None, description="Filter by specific supplier"),
    supplier_organization_id: Optional[str] = Query(None, description="Filter by supplier organization"),
):
    """
    Get document-level accuracy metrics.
    
    A document is considered accurate if ALL its system-preselected field values
    match the final values (case-insensitive comparison).
    """
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Build supplier filter
    supplier_filter = ""
    if ai_intake_only:
        supplier_filter += " AND sup.ai_intake_enabled = true"
    if supplier_id:
        supplier_filter += f" AND sup.external_id = '{supplier_id}'"
    
    base_ctes = build_base_ctes(start_date, end_date, supplier_filter, supplier_organization_id)
    
    query = f"""
        WITH {base_ctes},
        doc_accuracy AS (
            SELECT 
                csr_inbox_state_id,
                MIN(is_accurate) as all_fields_accurate
            FROM comparisons
            GROUP BY csr_inbox_state_id
        )
        SELECT 
            COUNT(*) as total_docs,
            SUM(all_fields_accurate) as accurate_docs
        FROM doc_accuracy
    """
    
    results = execute_query(query)
    
    total_docs = results[0]["total_docs"] if results else 0
    accurate_docs = results[0]["accurate_docs"] if (results and results[0]["accurate_docs"] is not None) else 0
    docs_with_changes = total_docs - accurate_docs
    accuracy_pct = round(100.0 * accurate_docs / total_docs, 2) if total_docs > 0 else 0
    
    return DocumentAccuracyResponse(
        total_ai_docs=total_docs,
        docs_with_edits=docs_with_changes,
        docs_no_edits=accurate_docs,
        accuracy_pct=accuracy_pct
    )


@router.get("/trend", response_model=AccuracyTrendResponse)
async def get_accuracy_trend(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    supplier_id: Optional[str] = Query(None, description="Filter by specific supplier"),
    supplier_organization_id: Optional[str] = Query(None, description="Filter by supplier organization"),
    period: str = Query("day", description="Aggregation period: day or week"),
):
    """
    Get accuracy trend over time.
    
    Returns daily or weekly accuracy percentages based on document-level accuracy
    (comparing initial system values to final values, case-insensitive).
    """
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Build supplier filter
    supplier_filter = ""
    if ai_intake_only:
        supplier_filter += " AND sup.ai_intake_enabled = true"
    if supplier_id:
        supplier_filter += f" AND sup.external_id = '{supplier_id}'"
    
    # Determine date truncation based on period
    if period == "week":
        date_trunc = "DATE_TRUNC('week', doc_date)"
    else:
        date_trunc = "DATE_TRUNC('day', doc_date)"
    
    base_ctes = build_base_ctes(start_date, end_date, supplier_filter, supplier_organization_id)
    
    query = f"""
        WITH {base_ctes},
        doc_accuracy AS (
            SELECT 
                csr_inbox_state_id,
                MIN(created_at) as doc_date,
                MIN(is_accurate) as all_fields_accurate
            FROM comparisons
            GROUP BY csr_inbox_state_id
        )
        SELECT 
            {date_trunc}::date as date,
            COUNT(*) as total_docs,
            SUM(CASE WHEN all_fields_accurate = 0 THEN 1 ELSE 0 END) as docs_with_changes,
            ROUND(100.0 * SUM(all_fields_accurate) / NULLIF(COUNT(*), 0), 2) as accuracy_pct
        FROM doc_accuracy
        GROUP BY 1
        ORDER BY 1
    """
    
    results = execute_query(query)
    
    trend_data = [
        AccuracyTrendPoint(
            date=row["date"],
            accuracy_pct=float(row["accuracy_pct"]) if row["accuracy_pct"] else 0,
            total_docs=row["total_docs"],
            docs_with_changes=row["docs_with_changes"]
        )
        for row in results
    ]
    
    # Calculate overall average
    total_docs = sum(p.total_docs for p in trend_data)
    total_changes = sum(p.docs_with_changes for p in trend_data)
    overall_accuracy = round(100.0 * (total_docs - total_changes) / total_docs, 2) if total_docs > 0 else 0
    
    return AccuracyTrendResponse(
        data=trend_data,
        overall_accuracy_pct=overall_accuracy,
        period=period
    )


@router.get("/field-level-trend", response_model=AccuracyTrendResponse)
async def get_field_level_accuracy_trend(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 90 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    supplier_id: Optional[str] = Query(None, description="Filter by specific supplier"),
    supplier_organization_id: Optional[str] = Query(None, description="Filter by supplier organization"),
    period: str = Query("day", description="Aggregation period: day or week"),
):
    """
    Get field-level accuracy trend over time.
    
    Calculates the weighted average accuracy across all field types for each time period.
    This shows the overall field accuracy (like overall_accuracy_pct in /per-field) over time.
    """
    
    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Build supplier filter
    supplier_filter = ""
    if ai_intake_only:
        supplier_filter += " AND sup.ai_intake_enabled = true"
    if supplier_id:
        supplier_filter += f" AND sup.external_id = '{supplier_id}'"
    
    # Determine date truncation based on period
    if period == "week":
        date_trunc = "DATE_TRUNC('week', created_at)"
    else:
        date_trunc = "DATE_TRUNC('day', created_at)"
    
    base_ctes = build_base_ctes(start_date, end_date, supplier_filter, supplier_organization_id)
    
    query = f"""
        WITH {base_ctes},
        field_accuracy_by_date AS (
            SELECT 
                {date_trunc}::date as date,
                record_type,
                field_identifier,
                COUNT(*) as total_docs,
                SUM(is_accurate) as accurate_docs
            FROM comparisons
            GROUP BY 1, 2, 3
            HAVING COUNT(*) > 10
        )
        SELECT 
            date,
            SUM(accurate_docs) as total_accurate,
            SUM(total_docs) as total_docs,
            ROUND(100.0 * SUM(accurate_docs) / NULLIF(SUM(total_docs), 0), 2) as accuracy_pct,
            SUM(total_docs) - SUM(accurate_docs) as docs_with_changes
        FROM field_accuracy_by_date
        WHERE date < DATE_TRUNC('week', CURRENT_DATE)
        GROUP BY 1
        ORDER BY 1
    """
    
    results = execute_query(query)
    
    trend_data = [
        AccuracyTrendPoint(
            date=row["date"],
            accuracy_pct=float(row["accuracy_pct"]) if row["accuracy_pct"] else 0,
            total_docs=row["total_docs"],
            docs_with_changes=row["docs_with_changes"]
        )
        for row in results
    ]
    
    # Calculate overall average
    total_docs = sum(p.total_docs for p in trend_data)
    total_changes = sum(p.docs_with_changes for p in trend_data)
    overall_accuracy = round(100.0 * (total_docs - total_changes) / total_docs, 2) if total_docs > 0 else 0
    
    return AccuracyTrendResponse(
        data=trend_data,
        overall_accuracy_pct=overall_accuracy,
        period=period
    )


@router.get("/trend/debug")
async def debug_trend_data(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    ai_intake_only: bool = Query(False),
    supplier_id: Optional[str] = Query(None),
    supplier_organization_id: Optional[str] = Query(None),
    period: str = Query("day"),
):
    """Debug endpoint to see raw trend data."""
    result = await get_accuracy_trend(start_date, end_date, ai_intake_only, supplier_id, supplier_organization_id, period)
    return {
        "data_points": len(result.data),
        "overall_accuracy": result.overall_accuracy_pct,
        "sample_data": result.data[:5] if result.data else [],
        "all_data": result.data
    }
