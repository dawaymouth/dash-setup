"""
Suppliers API endpoints.
"""
from fastapi import APIRouter, Query
from typing import Optional

from app.database import execute_query
from app.models import Supplier, SupplierListResponse, SupplierOrganization, SupplierOrganizationListResponse

router = APIRouter()


@router.get("/", response_model=SupplierListResponse)
async def list_suppliers(
    ai_intake_only: bool = Query(False, description="Filter to AI intake enabled suppliers only"),
    search: Optional[str] = Query(None, description="Search suppliers by name"),
):
    """List all suppliers with optional filtering.
    
    Uses analytics.intake_documents as the source of truth for supplier data
    and AI intake enablement status, ensuring accuracy based on actual activity.
    """
    
    # Build WHERE clauses
    where_clauses = ["id.supplier_id IS NOT NULL"]
    if search:
        where_clauses.append(f"LOWER(id.supplier) LIKE LOWER('%{search}%')")
    
    where_sql = f"WHERE {' AND '.join(where_clauses)}"
    
    # Build HAVING clause for AI intake filter
    having_clause = ""
    if ai_intake_only:
        having_clause = "HAVING MAX(CASE WHEN id.is_ai_intake_enabled = true THEN 1 ELSE 0 END)::boolean = true"
    
    query = f"""
        SELECT DISTINCT
            id.supplier_id,
            id.supplier as name,
            MAX(CASE WHEN id.is_ai_intake_enabled = true THEN 1 ELSE 0 END)::boolean as ai_intake_enabled
        FROM analytics.intake_documents id
        {where_sql}
        GROUP BY id.supplier_id, id.supplier
        {having_clause}
        ORDER BY name
        LIMIT 500
    """
    
    results = execute_query(query)
    
    suppliers = [
        Supplier(
            supplier_id=row["supplier_id"],
            name=row["name"] or "Unknown",
            ai_intake_enabled=row["ai_intake_enabled"]
        )
        for row in results
    ]
    
    return SupplierListResponse(
        data=suppliers,
        total=len(suppliers)
    )


@router.get("/ai-enabled-count")
async def get_ai_enabled_count():
    """Get count of AI intake enabled suppliers.
    
    Uses analytics.intake_documents to count suppliers with actual AI intake activity.
    """
    
    query = """
        SELECT COUNT(DISTINCT id.supplier_id) as count
        FROM analytics.intake_documents id
        WHERE id.supplier_id IS NOT NULL
          AND id.is_ai_intake_enabled = true
    """
    
    results = execute_query(query)
    
    return {"ai_enabled_count": results[0]["count"] if results else 0}


@router.get("/organizations", response_model=SupplierOrganizationListResponse)
async def list_supplier_organizations(
    ai_intake_only: bool = Query(False, description="Filter to organizations with AI intake enabled suppliers"),
    search: Optional[str] = Query(None, description="Search organizations by name"),
):
    """List all supplier organizations with optional filtering."""
    
    where_clauses = ["id.supplier_organization_id IS NOT NULL"]
    if search:
        where_clauses.append(f"LOWER(id.supplier_organization) LIKE LOWER('%{search}%')")
    
    where_sql = f"WHERE {' AND '.join(where_clauses)}"
    
    having_clause = ""
    if ai_intake_only:
        having_clause = "HAVING MAX(CASE WHEN id.is_ai_intake_enabled = true THEN 1 ELSE 0 END)::boolean = true"
    
    query = f"""
        SELECT DISTINCT
            id.supplier_organization_id,
            id.supplier_organization as name,
            COUNT(DISTINCT id.supplier_id) as num_suppliers,
            MAX(CASE WHEN id.is_ai_intake_enabled = true THEN 1 ELSE 0 END)::boolean as has_ai_intake
        FROM analytics.intake_documents id
        {where_sql}
        GROUP BY id.supplier_organization_id, id.supplier_organization
        {having_clause}
        ORDER BY name
        LIMIT 500
    """
    
    results = execute_query(query)
    
    organizations = [
        SupplierOrganization(
            organization_id=row["supplier_organization_id"],
            name=row["name"] or "Unknown",
            num_suppliers=row["num_suppliers"],
            has_ai_intake=row["has_ai_intake"]
        )
        for row in results
    ]
    
    return SupplierOrganizationListResponse(
        data=organizations,
        total=len(organizations)
    )
