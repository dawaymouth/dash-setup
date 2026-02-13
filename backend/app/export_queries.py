"""
SQL query builders for the full AI dashboard export (direct DB, no API).
Used by export_full_ai_dashboard.py. Mirrors router logic for volume, cycle time, productivity, accuracy.
"""
from datetime import date, timedelta
from typing import Optional

from app.cycle_time_sql import (
    build_received_to_open_business_hours_bulk_overall_query,
    build_received_to_open_business_hours_bulk_query,
    build_received_to_open_business_hours_overall_query,
    build_received_to_open_business_hours_query,
)
from app.database import execute_query


def date_filter_sql(start_date: date, end_date: date, column: str = "document_created_at") -> str:
    """WHERE fragment for date range."""
    return f"{column} >= '{start_date}' AND {column} < '{end_date + timedelta(days=1)}'"


def _org_in_list_sql(org_ids: list[str]) -> str:
    """supplier_organization_id IN (...)."""
    if not org_ids:
        return "1=0"
    escaped = [f"'{oid}'" for oid in org_ids]
    return f"supplier_organization_id IN ({','.join(escaped)})"


# ---------------------------------------------------------------------------
# Bulk queries (all AI orgs at once; caller groups by org)
# ---------------------------------------------------------------------------

def query_volume_by_day_bulk(start_date: date, end_date: date, org_ids: list[str]) -> list[dict]:
    """Volume by day for all given orgs. Returns rows with date, supplier_id, supplier_organization_id, count."""
    org_sql = _org_in_list_sql(org_ids)
    date_sql = date_filter_sql(start_date, end_date)
    query = f"""
        SELECT
            DATE_TRUNC('day', document_created_at)::date as date,
            supplier_id,
            supplier_organization_id,
            COUNT(*) as count
        FROM analytics.intake_documents
        WHERE {date_sql}
          AND {org_sql}
          AND is_ai_intake_enabled = true
        GROUP BY 1, 2, 3
        ORDER BY 3, 1, 2
    """
    return execute_query(query)


def query_categories_bulk(start_date: date, end_date: date, org_ids: list[str]) -> list[dict]:
    """Categories for all given orgs. Returns rows with supplier_organization_id, supplier_id, category, count."""
    if not org_ids:
        return []
    org_sql = "o.supplier_organization_id IN (" + ",".join(f"'{oid}'" for oid in org_ids) + ")"
    date_sql = f"o.created_at >= '{start_date}' AND o.created_at < '{end_date + timedelta(days=1)}'"
    query = f"""
        SELECT
            o.supplier_organization_id,
            o.supplier_id,
            COALESCE(os.category, 'Uncategorized') as category,
            COUNT(DISTINCT o.order_id) as count
        FROM analytics.orders o
        LEFT JOIN analytics.order_skus os ON o.order_id = os.order_id
        WHERE {date_sql}
          AND {org_sql}
        GROUP BY 1, 2, 3
        ORDER BY 1, 3 DESC
    """
    return execute_query(query)


def query_time_of_day_bulk(start_date: date, end_date: date, org_ids: list[str]) -> list[dict]:
    """Time-of-day rows for all given orgs. Returns supplier_organization_id, supplier_id, document_created_at."""
    org_sql = _org_in_list_sql(org_ids)
    date_sql = date_filter_sql(start_date, end_date)
    query = f"""
        SELECT
            supplier_organization_id,
            supplier_id,
            document_created_at AT TIME ZONE 'UTC' as document_created_at
        FROM analytics.intake_documents
        WHERE {date_sql}
          AND {org_sql}
          AND is_ai_intake_enabled = true
    """
    return execute_query(query)


def query_suppliers_bulk(org_ids: list[str]) -> list[dict]:
    """Suppliers for all given orgs (AI intake enabled only, per workflow.suppliers). Returns supplier_organization_id, supplier_id, name, ai_intake_enabled."""
    if not org_ids:
        return []
    org_sql = _org_in_list_sql(org_ids)
    query = f"""
        SELECT
            id.supplier_organization_id,
            id.supplier_id,
            id.supplier as name,
            sup.ai_intake_enabled
        FROM analytics.intake_documents id
        JOIN workflow.suppliers sup ON sup.external_id = id.supplier_id AND sup.ai_intake_enabled = true
        WHERE id.supplier_organization_id IN ({','.join(f"'{oid}'" for oid in org_ids)})
          AND id.supplier_id IS NOT NULL
        GROUP BY id.supplier_organization_id, id.supplier_id, id.supplier, sup.ai_intake_enabled
        ORDER BY id.supplier_organization_id, id.supplier
    """
    return execute_query(query)


def query_pages_org_bulk(start_date: date, end_date: date, org_ids: list[str]) -> list[dict]:
    """Pages (org-level) for all given orgs. Returns supplier_organization_id, total_documents, total_pages."""
    if not org_ids:
        return []
    date_sql = date_filter_sql(start_date, end_date, "id.document_created_at")
    org_sql = "id.supplier_organization_id IN (" + ",".join(f"'{oid}'" for oid in org_ids) + ")"
    query = f"""
        SELECT
            id.supplier_organization_id,
            COUNT(DISTINCT id.intake_document_id) as total_documents,
            COALESCE(SUM(d.page_count), 0) as total_pages
        FROM analytics.intake_documents id
        LEFT JOIN workflow.documents d ON d.external_id = id.document_id
        WHERE {org_sql} AND {date_sql} AND id.is_ai_intake_enabled = true
        GROUP BY id.supplier_organization_id
    """
    return execute_query(query)


def query_pages_by_supplier_bulk(start_date: date, end_date: date, org_ids: list[str]) -> list[dict]:
    """Pages by supplier for all given orgs. Returns supplier_organization_id, supplier_id, total_documents, total_pages."""
    if not org_ids:
        return []
    date_sql = date_filter_sql(start_date, end_date, "id.document_created_at")
    org_sql = "id.supplier_organization_id IN (" + ",".join(f"'{oid}'" for oid in org_ids) + ")"
    query = f"""
        SELECT
            id.supplier_organization_id,
            id.supplier_id,
            COUNT(DISTINCT id.intake_document_id) as total_documents,
            COALESCE(SUM(d.page_count), 0) as total_pages
        FROM analytics.intake_documents id
        LEFT JOIN workflow.documents d ON d.external_id = id.document_id
        WHERE {org_sql} AND {date_sql} AND id.supplier_id IS NOT NULL AND id.is_ai_intake_enabled = true
        GROUP BY id.supplier_organization_id, id.supplier_id
    """
    return execute_query(query)


# ---------------------------------------------------------------------------
# Per-org: volume-related (pages, pages by supplier)
# ---------------------------------------------------------------------------

def query_pages_org(org_id: str, start_date: date, end_date: date) -> dict:
    """Org-level pages stats. Returns single row: total_documents, total_pages."""
    date_sql = date_filter_sql(start_date, end_date, "id.document_created_at")
    query = f"""
        SELECT
            COUNT(DISTINCT id.intake_document_id) as total_documents,
            COALESCE(SUM(d.page_count), 0) as total_pages
        FROM analytics.intake_documents id
        LEFT JOIN workflow.documents d ON d.external_id = id.document_id
        WHERE id.supplier_organization_id = '{org_id}'
          AND {date_sql}
    """
    rows = execute_query(query)
    if not rows:
        return {"total_documents": 0, "total_pages": 0}
    r = rows[0]
    return {
        "total_documents": r["total_documents"] or 0,
        "total_pages": int(r["total_pages"] or 0),
    }


def query_pages_by_supplier(org_id: str, start_date: date, end_date: date) -> list[dict]:
    """One row per supplier: supplier_id, total_documents, total_pages."""
    date_sql = date_filter_sql(start_date, end_date, "id.document_created_at")
    query = f"""
        SELECT
            id.supplier_id,
            COUNT(DISTINCT id.intake_document_id) as total_documents,
            COALESCE(SUM(d.page_count), 0) as total_pages
        FROM analytics.intake_documents id
        LEFT JOIN workflow.documents d ON d.external_id = id.document_id
        WHERE id.supplier_organization_id = '{org_id}'
          AND {date_sql}
          AND id.supplier_id IS NOT NULL
        GROUP BY id.supplier_id
    """
    return execute_query(query)


# ---------------------------------------------------------------------------
# Bulk: document-level accuracy by supplier (needs CTE with org_id)
# ---------------------------------------------------------------------------

def _build_base_ctes_bulk(start_date: date, end_date: date, org_ids: list[str]) -> str:
    """Base CTEs for accuracy with multiple orgs; comparisons include supplier_organization_id."""
    if not org_ids:
        return "comparisons AS (SELECT 1 AS _dummy WHERE 1=0)"
    org_list = ",".join(f"'{oid}'" for oid in org_ids)
    return f"""
        first_values AS (
            SELECT a.csr_inbox_state_id, a.record_type, a.field_identifier, a.field_value, a.created_at,
                   id.supplier_id, id.supplier_organization_id,
                   ROW_NUMBER() OVER (PARTITION BY a.csr_inbox_state_id, a.field_identifier ORDER BY a.created_at ASC) as rn
            FROM workflow.csr_inbox_state_data_audits a
            JOIN workflow.csr_inbox_states s ON a.csr_inbox_state_id = s.id
            JOIN analytics.intake_documents id ON s.external_id = id.intake_document_id
            JOIN workflow.suppliers sup ON s.supplier_id = sup.id
            JOIN workflow.supplier_organizations so ON sup.supplier_organization_id = so.id
            WHERE a.user_id IS NULL
              AND a.created_at >= '{start_date}' AND a.created_at < '{end_date + timedelta(days=1)}'
              AND so.external_id IN ({org_list})
              AND id.is_ai_intake_enabled = true
        ),
        last_values AS (
            SELECT a.csr_inbox_state_id, a.field_identifier, a.field_value,
                   ROW_NUMBER() OVER (PARTITION BY a.csr_inbox_state_id, a.field_identifier ORDER BY a.created_at DESC) as rn
            FROM workflow.csr_inbox_state_data_audits a
            JOIN workflow.csr_inbox_states s ON a.csr_inbox_state_id = s.id
            JOIN analytics.intake_documents id ON s.external_id = id.intake_document_id
            JOIN workflow.suppliers sup ON s.supplier_id = sup.id
            JOIN workflow.supplier_organizations so ON sup.supplier_organization_id = so.id
            WHERE a.created_at >= '{start_date}' AND a.created_at < '{end_date + timedelta(days=1)}'
              AND so.external_id IN ({org_list})
              AND id.is_ai_intake_enabled = true
        ),
        comparisons AS (
            SELECT f.record_type, f.field_identifier, f.csr_inbox_state_id, f.created_at, f.supplier_id, f.supplier_organization_id,
                   CASE WHEN LOWER(COALESCE(f.field_value, '')) = LOWER(COALESCE(l.field_value, '')) THEN 1 ELSE 0 END as is_accurate
            FROM first_values f
            JOIN last_values l ON f.csr_inbox_state_id = l.csr_inbox_state_id AND f.field_identifier = l.field_identifier
            WHERE f.rn = 1 AND l.rn = 1
        )
    """


def query_document_accuracy_by_supplier_bulk(start_date: date, end_date: date, org_ids: list[str]) -> list[dict]:
    """Document-level accuracy per supplier for all orgs. Returns supplier_organization_id, supplier_id, total_ai_docs, docs_with_edits, docs_no_edits, accuracy_pct."""
    if not org_ids:
        return []
    base_ctes = _build_base_ctes_bulk(start_date, end_date, org_ids)
    query = f"""
        WITH {base_ctes},
        doc_accuracy AS (
            SELECT csr_inbox_state_id, supplier_organization_id, supplier_id, MIN(is_accurate) as all_fields_accurate
            FROM comparisons GROUP BY 1, 2, 3
        )
        SELECT supplier_organization_id, supplier_id,
               COUNT(*) as total_ai_docs,
               SUM(CASE WHEN all_fields_accurate = 0 THEN 1 ELSE 0 END) as docs_with_edits,
               SUM(all_fields_accurate) as docs_no_edits
        FROM doc_accuracy GROUP BY supplier_organization_id, supplier_id
    """
    rows = execute_query(query)
    result = []
    for r in rows:
        total = r["total_ai_docs"] or 0
        no_edits = int(r["docs_no_edits"] or 0)
        with_edits = int(r["docs_with_edits"] or 0)
        pct = round(100.0 * no_edits / total, 2) if total > 0 else 0
        result.append({
            "supplier_organization_id": r["supplier_organization_id"],
            "supplier_id": r["supplier_id"],
            "total_ai_docs": total,
            "docs_with_edits": with_edits,
            "docs_no_edits": no_edits,
            "accuracy_pct": pct,
        })
    return result


# ---------------------------------------------------------------------------
# Per-org: document-level accuracy by supplier
# ---------------------------------------------------------------------------

def query_document_accuracy_by_supplier(org_id: str, start_date: date, end_date: date) -> list[dict]:
    """Document-level accuracy per supplier. Uses same logic as accuracy router but GROUP BY supplier_id."""
    from app.routers.accuracy import build_base_ctes
    supplier_filter = ""
    base_ctes = build_base_ctes(start_date, end_date, supplier_filter, org_id)
    query = f"""
        WITH {base_ctes},
        doc_accuracy AS (
            SELECT
                csr_inbox_state_id,
                supplier_id,
                MIN(is_accurate) as all_fields_accurate
            FROM comparisons
            GROUP BY 1, 2
        )
        SELECT
            supplier_id,
            COUNT(*) as total_ai_docs,
            SUM(CASE WHEN all_fields_accurate = 0 THEN 1 ELSE 0 END) as docs_with_edits,
            SUM(all_fields_accurate) as docs_no_edits
        FROM doc_accuracy
        GROUP BY supplier_id
    """
    rows = execute_query(query)
    result = []
    for r in rows:
        total = r["total_ai_docs"] or 0
        no_edits = int(r["docs_no_edits"] or 0)
        with_edits = int(r["docs_with_edits"] or 0)
        pct = round(100.0 * no_edits / total, 2) if total > 0 else 0
        result.append({
            "supplier_id": r["supplier_id"],
            "total_ai_docs": total,
            "docs_with_edits": with_edits,
            "docs_no_edits": no_edits,
            "accuracy_pct": pct,
        })
    return result


# ---------------------------------------------------------------------------
# Per-org: cycle time (received_to_open, processing, state_distribution)
# ---------------------------------------------------------------------------

def query_cycle_received_to_open(org_id: str, start_date: date, end_date: date) -> tuple[list[dict], float]:
    """Per-day per-supplier median minutes; overall median. Uses business hours (8 AM–6 PM Mon–Fri), matching API and UI."""
    where_sql = (
        f"document_created_at >= '{start_date}' AND document_created_at < '{end_date + timedelta(days=1)}'"
        f" AND document_first_accessed_at IS NOT NULL"
        f" AND supplier_organization_id = '{org_id}'"
    )
    query = build_received_to_open_business_hours_query(where_sql)
    results = execute_query(query)
    data = [
        {"date": r["date"], "avg_minutes": round(float(r["avg_minutes"] or 0), 2), "count": r["count"], "supplier_id": r.get("supplier_id")}
        for r in results
    ]
    overall_q = build_received_to_open_business_hours_overall_query(where_sql)
    overall_rows = execute_query(overall_q)
    overall_median = round(float(overall_rows[0]["median_minutes"]), 2) if overall_rows and overall_rows[0].get("median_minutes") is not None else 0
    return data, overall_median


def query_cycle_processing(org_id: str, start_date: date, end_date: date) -> tuple[list[dict], float]:
    """Processing time: open to intake_updated_at."""
    where_sql = (
        f"document_created_at >= '{start_date}' AND document_created_at < '{end_date + timedelta(days=1)}'"
        f" AND document_first_accessed_at IS NOT NULL"
        f" AND state NOT IN ('new')"
        f" AND supplier_organization_id = '{org_id}'"
    )
    time_calc = "DATEDIFF(minute, document_first_accessed_at, intake_updated_at)"
    query = f"""
        SELECT
            DATE_TRUNC('day', document_created_at)::date AS date,
            supplier_id,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {time_calc}) AS avg_minutes,
            COUNT(*) AS count
        FROM analytics.intake_documents
        WHERE {where_sql}
          AND intake_updated_at > document_first_accessed_at
          AND {time_calc} > 0 AND {time_calc} < 1440
        GROUP BY 1, 2
        ORDER BY 1, 2
    """
    results = execute_query(query)
    data = [
        {"date": r["date"], "avg_minutes": round(float(r["avg_minutes"] or 0), 2), "count": r["count"], "supplier_id": r.get("supplier_id")}
        for r in results
    ]
    overall_q = f"""
        SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {time_calc}) AS median_minutes
        FROM analytics.intake_documents
        WHERE {where_sql} AND intake_updated_at > document_first_accessed_at AND {time_calc} > 0 AND {time_calc} < 1440
    """
    overall_rows = execute_query(overall_q)
    overall_median = round(float(overall_rows[0]["median_minutes"]), 2) if overall_rows and overall_rows[0].get("median_minutes") is not None else 0
    return data, overall_median


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


# ---------------------------------------------------------------------------
# Bulk: cycle time (received_to_open, processing, state_distribution)
# ---------------------------------------------------------------------------

def query_cycle_received_to_open_bulk(start_date: date, end_date: date, org_ids: list[str]) -> tuple[list[dict], dict]:
    """Bulk: rows with supplier_organization_id, date, supplier_id, avg_minutes, count; overall_by_org = median per org. Uses business hours (8 AM–6 PM Mon–Fri), matching API and UI."""
    if not org_ids:
        return [], {}
    org_sql = _org_in_list_sql(org_ids)
    where_sql = (
        f"document_created_at >= '{start_date}' AND document_created_at < '{end_date + timedelta(days=1)}'"
        f" AND document_first_accessed_at IS NOT NULL AND {org_sql} AND is_ai_intake_enabled = true"
    )
    query = build_received_to_open_business_hours_bulk_query(where_sql)
    rows = execute_query(query)
    data = []
    for r in rows:
        data.append({
            "supplier_organization_id": r["supplier_organization_id"],
            "date": r["date"],
            "supplier_id": r.get("supplier_id"),
            "avg_minutes": round(float(r["avg_minutes"] or 0), 2),
            "count": r["count"],
        })
    overall_q = build_received_to_open_business_hours_bulk_overall_query(where_sql)
    overall_rows = execute_query(overall_q)
    overall_by_org = {r["supplier_organization_id"]: round(float(r["median_minutes"] or 0), 2) for r in overall_rows}
    return data, overall_by_org


def query_cycle_processing_bulk(start_date: date, end_date: date, org_ids: list[str]) -> tuple[list[dict], dict]:
    """Bulk: rows with supplier_organization_id, date, supplier_id, avg_minutes, count; overall median per org."""
    if not org_ids:
        return [], {}
    org_sql = _org_in_list_sql(org_ids)
    where_sql = (
        f"document_created_at >= '{start_date}' AND document_created_at < '{end_date + timedelta(days=1)}'"
        f" AND document_first_accessed_at IS NOT NULL AND state NOT IN ('new') AND {org_sql} AND is_ai_intake_enabled = true"
    )
    time_calc = "DATEDIFF(minute, document_first_accessed_at, intake_updated_at)"
    query = f"""
        SELECT supplier_organization_id, DATE_TRUNC('day', document_created_at)::date AS date, supplier_id,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {time_calc}) AS avg_minutes, COUNT(*) AS count
        FROM analytics.intake_documents
        WHERE {where_sql} AND intake_updated_at > document_first_accessed_at AND {time_calc} > 0 AND {time_calc} < 1440
        GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
    """
    rows = execute_query(query)
    data = [{"supplier_organization_id": r["supplier_organization_id"], "date": r["date"], "supplier_id": r.get("supplier_id"),
             "avg_minutes": round(float(r["avg_minutes"] or 0), 2), "count": r["count"]} for r in rows]
    overall_q = f"""
        SELECT supplier_organization_id, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {time_calc}) AS median_minutes
        FROM analytics.intake_documents
        WHERE {where_sql} AND intake_updated_at > document_first_accessed_at AND {time_calc} > 0 AND {time_calc} < 1440
        GROUP BY supplier_organization_id
    """
    overall_rows = execute_query(overall_q)
    overall_by_org = {r["supplier_organization_id"]: round(float(r["median_minutes"] or 0), 2) for r in overall_rows}
    return data, overall_by_org


def _state_distribution_derived_state_sql() -> str:
    """Derived state for Document Outcomes: split assigned into attached_to_existing, generated_new, assigned_other."""
    return """
        CASE
            WHEN state = 'assigned' AND is_document_attached_to_existing_dme_order = true THEN 'attached_to_existing'
            WHEN state = 'assigned' AND is_document_generated_new_dme_order = true THEN 'generated_new'
            WHEN state = 'assigned' THEN 'assigned_other'
            WHEN state IN ('split', 'splitting') THEN 'split'
            ELSE state
        END
    """


def _state_distribution_column_missing(err: Exception) -> bool:
    """True if error looks like a missing column (e.g. new DME order columns not yet in Redshift)."""
    msg = str(err).lower()
    return "column" in msg and ("does not exist" in msg or "not found" in msg)


def query_cycle_state_distribution_bulk(start_date: date, end_date: date, org_ids: list[str]) -> list[dict]:
    """Bulk: one row per (supplier_organization_id, state, supplier_id) with count; caller aggregates to { data, total } per org."""
    if not org_ids:
        return []
    org_sql = _org_in_list_sql(org_ids)
    where_sql = (
        f"document_created_at >= '{start_date}' AND document_created_at < '{end_date + timedelta(days=1)}'"
        f" AND state IN ({','.join(repr(s) for s in INCLUDED_STATES)}) AND {org_sql} AND is_ai_intake_enabled = true"
    )
    derived = _state_distribution_derived_state_sql()
    query = f"""
        SELECT supplier_organization_id,
               {derived} AS state,
               supplier_id, COUNT(*) AS count
        FROM analytics.intake_documents WHERE {where_sql}
        GROUP BY 1, 2, 3 ORDER BY 1, 3 DESC
    """
    try:
        return execute_query(query)
    except Exception as e:
        if not _state_distribution_column_missing(e):
            raise
        query_fallback = f"""
            SELECT supplier_organization_id,
                   CASE WHEN state IN ('split', 'splitting') THEN 'split' ELSE state END AS state,
                   supplier_id, COUNT(*) AS count
            FROM analytics.intake_documents WHERE {where_sql}
            GROUP BY 1, 2, 3 ORDER BY 1, 3 DESC
        """
        return execute_query(query_fallback)


def query_cycle_state_distribution_by_user_bulk(
    start_date: date, end_date: date, org_ids: list[str]
) -> list[dict]:
    """Bulk: one row per (supplier_organization_id, user_id, state, supplier_id) with count; caller groups by org and user."""
    if not org_ids:
        return []
    org_sql = _org_in_list_sql(org_ids)
    where_sql = (
        f"d.document_created_at >= '{start_date}' AND d.document_created_at < '{end_date + timedelta(days=1)}'"
        f" AND d.state IN ({','.join(repr(s) for s in INCLUDED_STATES)}) AND {org_sql} AND d.is_ai_intake_enabled = true"
    )
    derived = _state_distribution_derived_state_sql()
    query = f"""
        WITH last_access AS (
            SELECT
                a.csr_inbox_state_id,
                u.external_id AS user_external_id,
                ROW_NUMBER() OVER (PARTITION BY a.csr_inbox_state_id ORDER BY a.last_accessed_at DESC) AS rn
            FROM workflow.csr_inbox_state_accesses a
            JOIN workflow.users u ON a.user_id = u.id
        ),
        doc_user AS (
            SELECT
                d.supplier_organization_id,
                la.user_external_id AS user_id,
                d.state,
                d.supplier_id,
                d.is_document_attached_to_existing_dme_order,
                d.is_document_generated_new_dme_order
            FROM analytics.intake_documents d
            JOIN workflow.csr_inbox_states s ON d.intake_document_id = s.external_id
            JOIN last_access la ON s.id = la.csr_inbox_state_id AND la.rn = 1
            WHERE {where_sql}
        )
        SELECT supplier_organization_id, user_id,
               {derived} AS state,
               supplier_id, COUNT(*) AS count
        FROM doc_user
        GROUP BY 1, 2, 3, 4
        ORDER BY 1, 2, 5 DESC
    """
    try:
        rows = execute_query(query)
        return [
            {
                "supplier_organization_id": r["supplier_organization_id"],
                "user_id": r["user_id"],
                "state": r["state"],
                "supplier_id": r.get("supplier_id"),
                "count": r["count"],
            }
            for r in rows
        ]
    except Exception as e:
        if not _state_distribution_column_missing(e):
            raise
        derived_fallback = "CASE WHEN state IN ('split', 'splitting') THEN 'split' ELSE state END"
        query_fallback = f"""
            WITH last_access AS (
                SELECT
                    a.csr_inbox_state_id,
                    u.external_id AS user_external_id,
                    ROW_NUMBER() OVER (PARTITION BY a.csr_inbox_state_id ORDER BY a.last_accessed_at DESC) AS rn
                FROM workflow.csr_inbox_state_accesses a
                JOIN workflow.users u ON a.user_id = u.id
            ),
            doc_user AS (
                SELECT
                    d.supplier_organization_id,
                    la.user_external_id AS user_id,
                    d.state,
                    d.supplier_id
                FROM analytics.intake_documents d
                JOIN workflow.csr_inbox_states s ON d.intake_document_id = s.external_id
                JOIN last_access la ON s.id = la.csr_inbox_state_id AND la.rn = 1
                WHERE {where_sql}
            )
            SELECT supplier_organization_id, user_id,
                   {derived_fallback} AS state,
                   supplier_id, COUNT(*) AS count
            FROM doc_user
            GROUP BY 1, 2, 3, 4
            ORDER BY 1, 2, 5 DESC
        """
        rows = execute_query(query_fallback)
        return [
            {
                "supplier_organization_id": r["supplier_organization_id"],
                "user_id": r["user_id"],
                "state": r["state"],
                "supplier_id": r.get("supplier_id"),
                "count": r["count"],
            }
            for r in rows
        ]


def query_cycle_state_distribution(org_id: str, start_date: date, end_date: date) -> dict:
    """State distribution: list of { state, label, count, percentage }, total. Assigned split into attached_to_existing, generated_new, assigned_other."""
    where_sql = (
        f"document_created_at >= '{start_date}' AND document_created_at < '{end_date + timedelta(days=1)}'"
        f" AND state IN ({','.join(repr(s) for s in INCLUDED_STATES)})"
        f" AND supplier_organization_id = '{org_id}'"
    )
    derived = _state_distribution_derived_state_sql()
    query = f"""
        SELECT
            {derived} AS state,
            supplier_id,
            COUNT(*) AS count
        FROM analytics.intake_documents
        WHERE {where_sql}
        GROUP BY 1, 2
        ORDER BY 3 DESC
    """
    try:
        results = execute_query(query)
    except Exception as e:
        if not _state_distribution_column_missing(e):
            raise
        query_fallback = f"""
            SELECT
                CASE WHEN state IN ('split', 'splitting') THEN 'split' ELSE state END AS state,
                supplier_id,
                COUNT(*) AS count
            FROM analytics.intake_documents
            WHERE {where_sql}
            GROUP BY 1, 2
            ORDER BY 3 DESC
        """
        results = execute_query(query_fallback)
    state_totals = {}
    for r in results:
        st = r["state"]
        state_totals[st] = state_totals.get(st, 0) + r["count"]
    total = sum(state_totals.values())
    data = [
        {"state": st, "label": STATE_LABELS.get(st, st.title()), "count": c, "percentage": round(c * 100.0 / total, 2) if total > 0 else 0}
        for st, c in sorted(state_totals.items(), key=lambda x: -x[1])
    ]
    return {"data": data, "total": total}


# ---------------------------------------------------------------------------
# Bulk: productivity (4 queries; caller limits to top N per org if needed)
# ---------------------------------------------------------------------------

def _productivity_where_bulk(start_date: date, end_date: date, org_ids: list[str]) -> str:
    if not org_ids:
        return "1=0"
    org_sql = "d.supplier_organization_id IN (" + ",".join(f"'{oid}'" for oid in org_ids) + ")"
    return f"d.document_created_at >= '{start_date}' AND d.document_created_at < '{end_date + timedelta(days=1)}' AND d.state NOT IN ('new') AND {org_sql} AND d.is_ai_intake_enabled = true"


def query_active_individuals_bulk(start_date: date, end_date: date, org_ids: list[str]) -> dict[str, int]:
    """
    Count distinct users who accessed at least one non-new document per org.
    Uses any access record (not just last accessor) - aligns with "Active Individuals".
    Returns {supplier_organization_id: active_individuals_count}.
    """
    if not org_ids:
        return {}
    where_sql = _productivity_where_bulk(start_date, end_date, org_ids)
    query = f"""
        SELECT d.supplier_organization_id, COUNT(DISTINCT u.external_id)::int as active_individuals
        FROM workflow.csr_inbox_state_accesses a
        JOIN workflow.csr_inbox_states s ON s.id = a.csr_inbox_state_id
        JOIN analytics.intake_documents d ON d.intake_document_id = s.external_id
        JOIN workflow.users u ON u.id = a.user_id
        WHERE {where_sql}
        GROUP BY d.supplier_organization_id
    """
    rows = execute_query(query)
    return {r["supplier_organization_id"]: r["active_individuals"] for r in rows}


def query_active_individuals_for_orgs(start_date: date, end_date: date, org_ids: list[str]) -> int:
    """
    Count distinct users who accessed at least one non-new document across all given orgs.
    Used for merged "All Supplier Orgs" slice.
    """
    if not org_ids:
        return 0
    where_sql = _productivity_where_bulk(start_date, end_date, org_ids)
    query = f"""
        SELECT COUNT(DISTINCT u.external_id)::int as active_individuals
        FROM workflow.csr_inbox_state_accesses a
        JOIN workflow.csr_inbox_states s ON s.id = a.csr_inbox_state_id
        JOIN analytics.intake_documents d ON d.intake_document_id = s.external_id
        JOIN workflow.users u ON u.id = a.user_id
        WHERE {where_sql}
    """
    rows = execute_query(query)
    return rows[0]["active_individuals"] if rows else 0


def query_productivity_by_individual_bulk(start_date: date, end_date: date, org_ids: list[str], limit_per_org: int = 50) -> list[dict]:
    """Bulk: rows with supplier_organization_id, user_id, user_name, supplier_id, total_processed, avg_per_day, median_minutes."""
    if not org_ids:
        return []
    where_sql = _productivity_where_bulk(start_date, end_date, org_ids)
    query = f"""
        WITH last_access AS (
            SELECT a.csr_inbox_state_id, a.user_id, u.external_id as user_external_id,
                   u.first_name || ' ' || u.last_name as user_name,
                   ROW_NUMBER() OVER (PARTITION BY a.csr_inbox_state_id ORDER BY a.last_accessed_at DESC) as rn
            FROM workflow.csr_inbox_state_accesses a JOIN workflow.users u ON a.user_id = u.id
        ),
        user_processing_times AS (
            SELECT d.supplier_organization_id, la.user_external_id, la.user_name, d.supplier_id,
                   CASE WHEN first_acc.user_id = last_acc.user_id AND first_acc.user_id IS NOT NULL
                        AND DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) > 0
                        AND DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) < 1440
                   THEN DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) ELSE NULL END as processing_minutes
            FROM analytics.intake_documents d
            JOIN workflow.csr_inbox_states s ON d.intake_document_id = s.external_id
            JOIN last_access la ON s.id = la.csr_inbox_state_id AND la.rn = 1
            LEFT JOIN (SELECT csr_inbox_state_id, user_id, created_at, ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY created_at ASC) as rn FROM workflow.csr_inbox_state_accesses) first_acc ON s.id = first_acc.csr_inbox_state_id AND first_acc.rn = 1
            LEFT JOIN (SELECT csr_inbox_state_id, user_id, last_accessed_at, ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY last_accessed_at DESC) as rn FROM workflow.csr_inbox_state_accesses) last_acc ON s.id = last_acc.csr_inbox_state_id AND last_acc.rn = 1
            WHERE {where_sql}
        ),
        ranked AS (
            SELECT supplier_organization_id, user_external_id as user_id, user_name, supplier_id,
                   COUNT(*) as total_processed, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY processing_minutes) as median_minutes,
                   ROW_NUMBER() OVER (PARTITION BY supplier_organization_id ORDER BY COUNT(*) DESC) as rn
            FROM user_processing_times GROUP BY 1, 2, 3, 4
        )
        SELECT supplier_organization_id, user_id, user_name, supplier_id, total_processed, median_minutes
        FROM ranked WHERE rn <= {limit_per_org} ORDER BY 1, 5 DESC
    """
    rows = execute_query(query)
    days = (end_date - start_date).days + 1
    return [
        {"supplier_organization_id": r["supplier_organization_id"], "user_id": r["user_id"], "user_name": r["user_name"] or "Unknown",
         "total_processed": r["total_processed"], "avg_per_day": round(r["total_processed"] / days, 2),
         "median_minutes": round(float(r["median_minutes"]), 1) if r.get("median_minutes") is not None else None, "supplier_id": r.get("supplier_id")}
        for r in rows
    ]


def query_productivity_daily_average_bulk(start_date: date, end_date: date, org_ids: list[str], limit_per_org: int = 50) -> list[dict]:
    if not org_ids:
        return []
    where_sql = _productivity_where_bulk(start_date, end_date, org_ids)
    query = f"""
        WITH last_access AS (
            SELECT a.csr_inbox_state_id, a.user_id, u.external_id as user_external_id, u.first_name || ' ' || u.last_name as user_name,
                   ROW_NUMBER() OVER (PARTITION BY a.csr_inbox_state_id ORDER BY a.last_accessed_at DESC) as rn
            FROM workflow.csr_inbox_state_accesses a JOIN workflow.users u ON a.user_id = u.id
        ),
        user_docs_with_times AS (
            SELECT d.supplier_organization_id, la.user_external_id, la.user_name, d.supplier_id, d.document_created_at,
                   CASE WHEN first_acc.user_id = last_acc.user_id AND first_acc.user_id IS NOT NULL
                        AND DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) > 0 AND DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) < 1440
                   THEN DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) ELSE NULL END as processing_minutes
            FROM analytics.intake_documents d
            JOIN workflow.csr_inbox_states s ON d.intake_document_id = s.external_id
            JOIN last_access la ON s.id = la.csr_inbox_state_id AND la.rn = 1
            LEFT JOIN (SELECT csr_inbox_state_id, user_id, created_at, ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY created_at ASC) as rn FROM workflow.csr_inbox_state_accesses) first_acc ON s.id = first_acc.csr_inbox_state_id AND first_acc.rn = 1
            LEFT JOIN (SELECT csr_inbox_state_id, user_id, last_accessed_at, ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY last_accessed_at DESC) as rn FROM workflow.csr_inbox_state_accesses) last_acc ON s.id = last_acc.csr_inbox_state_id AND last_acc.rn = 1
            WHERE {where_sql}
        ),
        daily_counts AS (
            SELECT supplier_organization_id, user_external_id as user_id, user_name, supplier_id, DATE_TRUNC('day', document_created_at)::date as work_date,
                   COUNT(*) as daily_count, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY processing_minutes) as daily_median_minutes
            FROM user_docs_with_times GROUP BY 1, 2, 3, 4, 5
        ),
        agg AS (
            SELECT supplier_organization_id, user_id, user_name, supplier_id, SUM(daily_count) as total_processed, AVG(daily_count) as avg_per_day,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY daily_median_minutes) as median_minutes,
                   ROW_NUMBER() OVER (PARTITION BY supplier_organization_id ORDER BY AVG(daily_count) DESC) as rn
            FROM daily_counts GROUP BY 1, 2, 3, 4
        )
        SELECT supplier_organization_id, user_id, user_name, supplier_id, total_processed, avg_per_day, median_minutes
        FROM agg WHERE rn <= {limit_per_org} ORDER BY 1, 6 DESC
    """
    rows = execute_query(query)
    return [
        {"supplier_organization_id": r["supplier_organization_id"], "user_id": r["user_id"], "user_name": r["user_name"] or "Unknown",
         "total_processed": r["total_processed"], "avg_per_day": round(float(r["avg_per_day"] or 0), 2),
         "median_minutes": round(float(r["median_minutes"]), 1) if r.get("median_minutes") is not None else None, "supplier_id": r.get("supplier_id")}
        for r in rows
    ]


def query_productivity_by_individual_processing_time_bulk(start_date: date, end_date: date, org_ids: list[str], limit_per_org: int = 50) -> list[dict]:
    if not org_ids:
        return []
    where_sql = _productivity_where_bulk(start_date, end_date, org_ids)
    query = f"""
        WITH same_user_docs AS (
            SELECT d.supplier_organization_id, d.intake_document_id, d.supplier_id, first_acc.user_id,
                   u.external_id as user_external_id, u.first_name || ' ' || u.last_name as user_name,
                   DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) as processing_minutes
            FROM analytics.intake_documents d
            JOIN workflow.csr_inbox_states s ON d.intake_document_id = s.external_id
            LEFT JOIN (SELECT csr_inbox_state_id, user_id, created_at, ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY created_at ASC) as rn FROM workflow.csr_inbox_state_accesses) first_acc ON s.id = first_acc.csr_inbox_state_id AND first_acc.rn = 1
            LEFT JOIN (SELECT csr_inbox_state_id, user_id, last_accessed_at, ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY last_accessed_at DESC) as rn FROM workflow.csr_inbox_state_accesses) last_acc ON s.id = last_acc.csr_inbox_state_id AND last_acc.rn = 1
            LEFT JOIN workflow.users u ON first_acc.user_id = u.id
            WHERE {where_sql} AND first_acc.user_id = last_acc.user_id AND first_acc.user_id IS NOT NULL AND DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) > 0 AND DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) < 1440
        ),
        ranked AS (
            SELECT supplier_organization_id, user_external_id as user_id, user_name, supplier_id, COUNT(*) as total_processed,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY processing_minutes) as median_minutes,
                   ROW_NUMBER() OVER (PARTITION BY supplier_organization_id ORDER BY PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY processing_minutes) ASC) as rn
            FROM same_user_docs GROUP BY 1, 2, 3, 4 HAVING COUNT(*) >= 5
        )
        SELECT supplier_organization_id, user_id, user_name, supplier_id, total_processed, median_minutes
        FROM ranked WHERE rn <= {limit_per_org} ORDER BY 1, 6 ASC
    """
    rows = execute_query(query)
    days = (end_date - start_date).days + 1
    return [
        {"supplier_organization_id": r["supplier_organization_id"], "user_id": r["user_id"], "user_name": r["user_name"] or "Unknown",
         "total_processed": r["total_processed"], "avg_per_day": round(r["total_processed"] / days, 1),
         "median_minutes": round(float(r["median_minutes"]), 1) if r.get("median_minutes") is not None else None, "supplier_id": r.get("supplier_id")}
        for r in rows
    ]


def query_productivity_category_breakdown_bulk(start_date: date, end_date: date, org_ids: list[str], limit_per_org: int = 20) -> list[dict]:
    """Bulk: category breakdown by last accessor (workflow users.external_id) and document categories (workflow catalog).
    Same user_id as by_individual so static export user drill-down finds category rows."""
    if not org_ids:
        return []
    where_sql = _productivity_where_bulk(start_date, end_date, org_ids)
    query = f"""
        WITH last_access AS (
            SELECT a.csr_inbox_state_id, u.external_id AS user_external_id,
                   u.first_name || ' ' || u.last_name AS user_name,
                   ROW_NUMBER() OVER (PARTITION BY a.csr_inbox_state_id ORDER BY a.last_accessed_at DESC) AS rn
            FROM workflow.csr_inbox_state_accesses a
            JOIN workflow.users u ON a.user_id = u.id
        ),
        docs_with_user_and_cat AS (
            SELECT d.supplier_organization_id, la.user_external_id AS user_id, la.user_name, d.supplier_id,
                   COALESCE(cat.name, 'Uncategorized') AS category
            FROM analytics.intake_documents d
            JOIN workflow.csr_inbox_states s ON d.intake_document_id = s.external_id
            JOIN last_access la ON s.id = la.csr_inbox_state_id AND la.rn = 1
            LEFT JOIN workflow.csr_inbox_state_categories state_cat ON s.id = state_cat.csr_inbox_state_id
            LEFT JOIN workflow.catalog_categories cat ON state_cat.catalog_category_id = cat.id
            WHERE {where_sql}
        ),
        user_totals AS (
            SELECT supplier_organization_id, user_id, user_name, supplier_id, COUNT(*) AS total,
                   ROW_NUMBER() OVER (PARTITION BY supplier_organization_id ORDER BY COUNT(*) DESC) AS rn
            FROM docs_with_user_and_cat
            GROUP BY 1, 2, 3, 4
        ),
        top_users AS (
            SELECT supplier_organization_id, user_id, user_name, supplier_id, total
            FROM user_totals WHERE rn <= {limit_per_org}
        ),
        category_counts AS (
            SELECT dw.supplier_organization_id, dw.user_id, dw.user_name, dw.supplier_id, dw.category, COUNT(*) AS count
            FROM docs_with_user_and_cat dw
            WHERE (dw.supplier_organization_id, dw.user_id, dw.supplier_id) IN (
                SELECT supplier_organization_id, user_id, supplier_id FROM top_users
            )
            GROUP BY 1, 2, 3, 4, 5
        )
        SELECT cc.supplier_organization_id, cc.user_id, cc.user_name, cc.supplier_id, cc.category, cc.count,
               ROUND(cc.count * 100.0 / tu.total, 2) AS percentage
        FROM category_counts cc
        JOIN top_users tu ON cc.supplier_organization_id = tu.supplier_organization_id AND cc.user_id = tu.user_id AND cc.supplier_id = tu.supplier_id
        ORDER BY cc.supplier_organization_id, cc.user_name, cc.count DESC
    """
    rows = execute_query(query)
    return [
        {"supplier_organization_id": r["supplier_organization_id"], "user_id": r["user_id"], "user_name": r["user_name"] or "Unknown",
         "category": r["category"], "count": r["count"], "percentage": float(r["percentage"] or 0), "supplier_id": r.get("supplier_id")}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Per-org: productivity (4 queries)
# ---------------------------------------------------------------------------

def query_productivity_by_individual(org_id: str, start_date: date, end_date: date, limit: int = 50) -> list[dict]:
    where_sql = (
        f"d.document_created_at >= '{start_date}' AND d.document_created_at < '{end_date + timedelta(days=1)}'"
        f" AND d.state NOT IN ('new') AND d.supplier_organization_id = '{org_id}'"
    )
    query = f"""
        WITH last_access AS (
            SELECT a.csr_inbox_state_id, a.user_id, u.external_id as user_external_id,
                   u.first_name || ' ' || u.last_name as user_name,
                   ROW_NUMBER() OVER (PARTITION BY a.csr_inbox_state_id ORDER BY a.last_accessed_at DESC) as rn
            FROM workflow.csr_inbox_state_accesses a
            JOIN workflow.users u ON a.user_id = u.id
        ),
        user_processing_times AS (
            SELECT la.user_external_id, la.user_name, d.supplier_id,
                   CASE WHEN first_acc.user_id = last_acc.user_id AND first_acc.user_id IS NOT NULL
                        AND DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) > 0
                        AND DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) < 1440
                   THEN DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) ELSE NULL END as processing_minutes
            FROM analytics.intake_documents d
            JOIN workflow.csr_inbox_states s ON d.intake_document_id = s.external_id
            JOIN last_access la ON s.id = la.csr_inbox_state_id AND la.rn = 1
            LEFT JOIN (SELECT csr_inbox_state_id, user_id, created_at, ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY created_at ASC) as rn FROM workflow.csr_inbox_state_accesses) first_acc ON s.id = first_acc.csr_inbox_state_id AND first_acc.rn = 1
            LEFT JOIN (SELECT csr_inbox_state_id, user_id, last_accessed_at, ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY last_accessed_at DESC) as rn FROM workflow.csr_inbox_state_accesses) last_acc ON s.id = last_acc.csr_inbox_state_id AND last_acc.rn = 1
            WHERE {where_sql}
        )
        SELECT user_external_id as user_id, user_name, supplier_id,
               COUNT(*) as total_processed,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY processing_minutes) as median_minutes
        FROM user_processing_times
        GROUP BY 1, 2, 3
        ORDER BY 4 DESC
        LIMIT {limit}
    """
    rows = execute_query(query)
    days = (end_date - start_date).days + 1
    return [
        {"user_id": r["user_id"], "user_name": r["user_name"] or "Unknown", "total_processed": r["total_processed"],
         "avg_per_day": round(r["total_processed"] / days, 2), "median_minutes": round(float(r["median_minutes"]), 1) if r.get("median_minutes") is not None else None, "supplier_id": r.get("supplier_id")}
        for r in rows
    ]


def query_productivity_daily_average(org_id: str, start_date: date, end_date: date, limit: int = 50) -> list[dict]:
    where_sql = (
        f"d.document_created_at >= '{start_date}' AND d.document_created_at < '{end_date + timedelta(days=1)}'"
        f" AND d.state NOT IN ('new') AND d.supplier_organization_id = '{org_id}'"
    )
    query = f"""
        WITH last_access AS (
            SELECT a.csr_inbox_state_id, a.user_id, u.external_id as user_external_id, u.first_name || ' ' || u.last_name as user_name,
                   ROW_NUMBER() OVER (PARTITION BY a.csr_inbox_state_id ORDER BY a.last_accessed_at DESC) as rn
            FROM workflow.csr_inbox_state_accesses a JOIN workflow.users u ON a.user_id = u.id
        ),
        user_docs_with_times AS (
            SELECT la.user_external_id, la.user_name, d.supplier_id, d.document_created_at,
                   CASE WHEN first_acc.user_id = last_acc.user_id AND first_acc.user_id IS NOT NULL
                        AND DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) > 0 AND DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) < 1440
                   THEN DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) ELSE NULL END as processing_minutes
            FROM analytics.intake_documents d
            JOIN workflow.csr_inbox_states s ON d.intake_document_id = s.external_id
            JOIN last_access la ON s.id = la.csr_inbox_state_id AND la.rn = 1
            LEFT JOIN (SELECT csr_inbox_state_id, user_id, created_at, ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY created_at ASC) as rn FROM workflow.csr_inbox_state_accesses) first_acc ON s.id = first_acc.csr_inbox_state_id AND first_acc.rn = 1
            LEFT JOIN (SELECT csr_inbox_state_id, user_id, last_accessed_at, ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY last_accessed_at DESC) as rn FROM workflow.csr_inbox_state_accesses) last_acc ON s.id = last_acc.csr_inbox_state_id AND last_acc.rn = 1
            WHERE {where_sql}
        ),
        daily_counts AS (
            SELECT user_external_id as user_id, user_name, supplier_id, DATE_TRUNC('day', document_created_at)::date as work_date,
                   COUNT(*) as daily_count, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY processing_minutes) as daily_median_minutes
            FROM user_docs_with_times GROUP BY 1, 2, 3, 4
        )
        SELECT user_id, user_name, supplier_id, SUM(daily_count) as total_processed, AVG(daily_count) as avg_per_day,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY daily_median_minutes) as median_minutes
        FROM daily_counts GROUP BY 1, 2, 3 ORDER BY avg_per_day DESC LIMIT {limit}
    """
    rows = execute_query(query)
    return [
        {"user_id": r["user_id"], "user_name": r["user_name"] or "Unknown", "total_processed": r["total_processed"],
         "avg_per_day": round(float(r["avg_per_day"] or 0), 2), "median_minutes": round(float(r["median_minutes"]), 1) if r.get("median_minutes") is not None else None, "supplier_id": r.get("supplier_id")}
        for r in rows
    ]


def query_productivity_by_individual_processing_time(org_id: str, start_date: date, end_date: date, limit: int = 50) -> list[dict]:
    where_sql = (
        f"d.document_created_at >= '{start_date}' AND d.document_created_at < '{end_date + timedelta(days=1)}'"
        f" AND d.state NOT IN ('new') AND d.supplier_organization_id = '{org_id}'"
    )
    query = f"""
        WITH same_user_docs AS (
            SELECT d.intake_document_id, d.supplier_id, first_acc.user_id,
                   u.external_id as user_external_id, u.first_name || ' ' || u.last_name as user_name,
                   DATEDIFF(minute, first_acc.created_at, last_acc.last_accessed_at) as processing_minutes
            FROM analytics.intake_documents d
            JOIN workflow.csr_inbox_states s ON d.intake_document_id = s.external_id
            LEFT JOIN (SELECT csr_inbox_state_id, user_id, created_at, ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY created_at ASC) as rn FROM workflow.csr_inbox_state_accesses) first_acc ON s.id = first_acc.csr_inbox_state_id AND first_acc.rn = 1
            LEFT JOIN (SELECT csr_inbox_state_id, user_id, last_accessed_at, ROW_NUMBER() OVER (PARTITION BY csr_inbox_state_id ORDER BY last_accessed_at DESC) as rn FROM workflow.csr_inbox_state_accesses) last_acc ON s.id = last_acc.csr_inbox_state_id AND last_acc.rn = 1
            LEFT JOIN workflow.users u ON first_acc.user_id = u.id
            WHERE {where_sql} AND first_acc.user_id = last_acc.user_id AND first_acc.user_id IS NOT NULL AND processing_minutes > 0 AND processing_minutes < 1440
        )
        SELECT user_external_id as user_id, user_name, supplier_id, COUNT(*) as total_processed,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY processing_minutes) as median_minutes
        FROM same_user_docs GROUP BY 1, 2, 3 HAVING COUNT(*) >= 5 ORDER BY 5 ASC LIMIT {limit}
    """
    rows = execute_query(query)
    days = (end_date - start_date).days + 1
    return [
        {"user_id": r["user_id"], "user_name": r["user_name"] or "Unknown", "total_processed": r["total_processed"],
         "avg_per_day": round(r["total_processed"] / days, 1), "median_minutes": round(float(r["median_minutes"]), 1) if r.get("median_minutes") is not None else None, "supplier_id": r.get("supplier_id")}
        for r in rows
    ]


def query_productivity_category_breakdown(org_id: str, start_date: date, end_date: date, limit: int = 20) -> list[dict]:
    where_sql = (
        f"o.created_at >= '{start_date}' AND o.created_at < '{end_date + timedelta(days=1)}'"
        f" AND o.assignee_id IS NOT NULL AND o.supplier_organization_id = '{org_id}'"
    )
    query = f"""
        WITH individual_totals AS (
            SELECT o.assignee_id as user_id, o.assignee as user_name, o.supplier_id, COUNT(*) as total_orders
            FROM analytics.orders o LEFT JOIN interim.suppliers s ON o.supplier_id = s.external_id
            WHERE {where_sql}
            GROUP BY 1, 2, 3 ORDER BY 4 DESC LIMIT {limit}
        ),
        category_counts AS (
            SELECT o.assignee_id as user_id, o.assignee as user_name, o.supplier_id, COALESCE(os.category, 'Uncategorized') as category, COUNT(DISTINCT o.order_id) as count
            FROM analytics.orders o LEFT JOIN analytics.order_skus os ON o.order_id = os.order_id LEFT JOIN interim.suppliers s ON o.supplier_id = s.external_id
            WHERE {where_sql} AND o.assignee_id IN (SELECT user_id FROM individual_totals)
            GROUP BY 1, 2, 3, 4
        )
        SELECT cc.user_id, cc.user_name, cc.supplier_id, cc.category, cc.count, ROUND(cc.count * 100.0 / it.total_orders, 2) as percentage
        FROM category_counts cc JOIN individual_totals it ON cc.user_id = it.user_id AND cc.supplier_id = it.supplier_id
        ORDER BY cc.user_name, cc.count DESC
    """
    rows = execute_query(query)
    return [
        {"user_id": r["user_id"], "user_name": r["user_name"] or "Unknown", "category": r["category"], "count": r["count"], "percentage": float(r["percentage"] or 0), "supplier_id": r.get("supplier_id")}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Bulk: accuracy (per_field, document_level, trend, field_level_trend)
# ---------------------------------------------------------------------------

def query_accuracy_per_field_bulk(start_date: date, end_date: date, org_ids: list[str]) -> tuple[list[dict], dict]:
    """Bulk: rows with supplier_organization_id, record_type, field_identifier, supplier_id, total_docs, accurate_docs, accuracy_pct; overall_by_org in Python."""
    if not org_ids:
        return [], {}
    base_ctes = _build_base_ctes_bulk(start_date, end_date, org_ids)
    query = f"""
        WITH {base_ctes}
        SELECT supplier_organization_id, record_type, field_identifier, supplier_id, COUNT(*) as total_docs, SUM(is_accurate) as accurate_docs,
               ROUND(100.0 * SUM(is_accurate) / NULLIF(COUNT(*), 0), 2) as accuracy_pct
        FROM comparisons GROUP BY 1, 2, 3, 4 HAVING COUNT(*) > 10 ORDER BY 1, accuracy_pct ASC
    """
    rows = execute_query(query)
    data = [{"supplier_organization_id": r["supplier_organization_id"], "record_type": r["record_type"], "field_identifier": r["field_identifier"],
             "total_docs": r["total_docs"], "accurate_docs": r["accurate_docs"], "accuracy_pct": float(r["accuracy_pct"] or 0), "supplier_id": r.get("supplier_id")} for r in rows]
    overall_by_org = {}
    for oid in org_ids:
        org_rows = [r for r in data if r["supplier_organization_id"] == oid]
        total_docs = sum(r["total_docs"] for r in org_rows)
        total_acc = sum(r["accurate_docs"] for r in org_rows)
        overall_by_org[oid] = round(100.0 * total_acc / total_docs, 2) if total_docs > 0 else 0
    return data, overall_by_org


def query_accuracy_document_level_org_bulk(start_date: date, end_date: date, org_ids: list[str]) -> list[dict]:
    """Bulk: one row per org with total_ai_docs, docs_with_edits, docs_no_edits, accuracy_pct."""
    if not org_ids:
        return []
    base_ctes = _build_base_ctes_bulk(start_date, end_date, org_ids)
    query = f"""
        WITH {base_ctes},
        doc_accuracy AS (SELECT csr_inbox_state_id, supplier_organization_id, MIN(is_accurate) as all_fields_accurate FROM comparisons GROUP BY 1, 2)
        SELECT supplier_organization_id, COUNT(*) as total_docs, SUM(all_fields_accurate) as accurate_docs FROM doc_accuracy GROUP BY supplier_organization_id
    """
    rows = execute_query(query)
    result = []
    for r in rows:
        total = r["total_docs"] or 0
        no_edits = int(r["accurate_docs"] or 0)
        with_edits = total - no_edits
        result.append({
            "supplier_organization_id": r["supplier_organization_id"],
            "total_ai_docs": total,
            "docs_with_edits": with_edits,
            "docs_no_edits": no_edits,
            "accuracy_pct": round(100.0 * no_edits / total, 2) if total > 0 else 0,
        })
    return result


def query_accuracy_trend_bulk(start_date: date, end_date: date, org_ids: list[str], period: str = "week") -> tuple[list[dict], dict]:
    """Bulk: rows with supplier_organization_id, date, supplier_id, ...; overall_by_org in Python."""
    if not org_ids:
        return [], {}
    base_ctes = _build_base_ctes_bulk(start_date, end_date, org_ids)
    date_trunc = "DATE_TRUNC('week', doc_date)" if period == "week" else "DATE_TRUNC('day', doc_date)"
    query = f"""
        WITH {base_ctes},
        doc_accuracy AS (
            SELECT csr_inbox_state_id, supplier_organization_id, supplier_id, MIN(created_at) as doc_date, MIN(is_accurate) as all_fields_accurate
            FROM comparisons GROUP BY 1, 2, 3
        )
        SELECT supplier_organization_id, {date_trunc}::date as date, supplier_id, COUNT(*) as total_docs,
               SUM(CASE WHEN all_fields_accurate = 0 THEN 1 ELSE 0 END) as docs_with_changes,
               ROUND(100.0 * SUM(all_fields_accurate) / NULLIF(COUNT(*), 0), 2) as accuracy_pct
        FROM doc_accuracy GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
    """
    rows = execute_query(query)
    data = [{"supplier_organization_id": r["supplier_organization_id"], "date": r["date"], "accuracy_pct": float(r["accuracy_pct"] or 0),
             "total_docs": r["total_docs"], "docs_with_changes": r["docs_with_changes"], "supplier_id": r.get("supplier_id")} for r in rows]
    overall_by_org = {}
    for oid in org_ids:
        org_rows = [r for r in data if r["supplier_organization_id"] == oid]
        total_docs = sum(r["total_docs"] for r in org_rows)
        total_changes = sum(r["docs_with_changes"] for r in org_rows)
        overall_by_org[oid] = round(100.0 * (total_docs - total_changes) / total_docs, 2) if total_docs > 0 else 0
    return data, overall_by_org


def query_accuracy_field_level_trend_bulk(start_date: date, end_date: date, org_ids: list[str], period: str = "week") -> tuple[list[dict], dict]:
    if not org_ids:
        return [], {}
    base_ctes = _build_base_ctes_bulk(start_date, end_date, org_ids)
    date_trunc = "DATE_TRUNC('week', created_at)" if period == "week" else "DATE_TRUNC('day', created_at)"
    query = f"""
        WITH {base_ctes},
        field_accuracy_by_date AS (
            SELECT {date_trunc}::date as date, supplier_organization_id, supplier_id, record_type, field_identifier, COUNT(*) as total_docs, SUM(is_accurate) as accurate_docs
            FROM comparisons GROUP BY 1, 2, 3, 4, 5 HAVING COUNT(*) > 10
        )
        SELECT date, supplier_organization_id, supplier_id, SUM(accurate_docs) as total_accurate, SUM(total_docs) as total_docs,
               ROUND(100.0 * SUM(accurate_docs) / NULLIF(SUM(total_docs), 0), 2) as accuracy_pct,
               SUM(total_docs) - SUM(accurate_docs) as docs_with_changes
        FROM field_accuracy_by_date WHERE date < DATE_TRUNC('week', CURRENT_DATE) GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
    """
    rows = execute_query(query)
    data = [{"date": r["date"], "supplier_organization_id": r["supplier_organization_id"], "accuracy_pct": float(r["accuracy_pct"] or 0),
             "total_docs": r["total_docs"], "docs_with_changes": r["docs_with_changes"], "supplier_id": r.get("supplier_id")} for r in rows]
    overall_by_org = {}
    for oid in org_ids:
        org_rows = [r for r in data if r["supplier_organization_id"] == oid]
        total_docs = sum(r["total_docs"] for r in org_rows)
        total_changes = sum(r["docs_with_changes"] for r in org_rows)
        overall_by_org[oid] = round(100.0 * (total_docs - total_changes) / total_docs, 2) if total_docs > 0 else 0
    return data, overall_by_org


# ---------------------------------------------------------------------------
# Per-org: accuracy (per_field, document_level org, trend, field_level_trend)
# ---------------------------------------------------------------------------

def query_accuracy_per_field(org_id: str, start_date: date, end_date: date) -> tuple[list[dict], float]:
    from app.routers.accuracy import build_base_ctes
    base_ctes = build_base_ctes(start_date, end_date, "", org_id)
    query = f"""
        WITH {base_ctes}
        SELECT record_type, field_identifier, supplier_id, COUNT(*) as total_docs, SUM(is_accurate) as accurate_docs,
               ROUND(100.0 * SUM(is_accurate) / NULLIF(COUNT(*), 0), 2) as accuracy_pct
        FROM comparisons GROUP BY 1, 2, 3 HAVING COUNT(*) > 10 ORDER BY accuracy_pct ASC
    """
    rows = execute_query(query)
    data = [{"record_type": r["record_type"], "field_identifier": r["field_identifier"], "total_docs": r["total_docs"], "accurate_docs": r["accurate_docs"], "accuracy_pct": float(r["accuracy_pct"] or 0), "supplier_id": r.get("supplier_id")} for r in rows]
    total_docs = sum(r["total_docs"] for r in data)
    total_acc = sum(r["accurate_docs"] for r in data)
    overall = round(100.0 * total_acc / total_docs, 2) if total_docs > 0 else 0
    return data, overall


def query_accuracy_document_level_org(org_id: str, start_date: date, end_date: date) -> dict:
    from app.routers.accuracy import build_base_ctes
    base_ctes = build_base_ctes(start_date, end_date, "", org_id)
    query = f"""
        WITH {base_ctes},
        doc_accuracy AS (SELECT csr_inbox_state_id, MIN(is_accurate) as all_fields_accurate FROM comparisons GROUP BY csr_inbox_state_id)
        SELECT COUNT(*) as total_docs, SUM(all_fields_accurate) as accurate_docs FROM doc_accuracy
    """
    rows = execute_query(query)
    if not rows:
        return {"total_ai_docs": 0, "docs_with_edits": 0, "docs_no_edits": 0, "accuracy_pct": 0}
    r = rows[0]
    total = r["total_docs"] or 0
    no_edits = int(r["accurate_docs"] or 0)
    with_edits = total - no_edits
    return {"total_ai_docs": total, "docs_with_edits": with_edits, "docs_no_edits": no_edits, "accuracy_pct": round(100.0 * no_edits / total, 2) if total > 0 else 0}


def query_accuracy_trend(org_id: str, start_date: date, end_date: date, period: str = "week") -> tuple[list[dict], float]:
    from app.routers.accuracy import build_base_ctes
    date_trunc = "DATE_TRUNC('week', doc_date)" if period == "week" else "DATE_TRUNC('day', doc_date)"
    base_ctes = build_base_ctes(start_date, end_date, "", org_id)
    query = f"""
        WITH {base_ctes},
        doc_accuracy AS (
            SELECT csr_inbox_state_id, supplier_id, MIN(created_at) as doc_date, MIN(is_accurate) as all_fields_accurate
            FROM comparisons GROUP BY 1, 2
        )
        SELECT {date_trunc}::date as date, supplier_id, COUNT(*) as total_docs,
               SUM(CASE WHEN all_fields_accurate = 0 THEN 1 ELSE 0 END) as docs_with_changes,
               ROUND(100.0 * SUM(all_fields_accurate) / NULLIF(COUNT(*), 0), 2) as accuracy_pct
        FROM doc_accuracy GROUP BY 1, 2 ORDER BY 1, 2
    """
    rows = execute_query(query)
    data = [{"date": r["date"], "accuracy_pct": float(r["accuracy_pct"] or 0), "total_docs": r["total_docs"], "docs_with_changes": r["docs_with_changes"], "supplier_id": r.get("supplier_id")} for r in rows]
    total_docs = sum(r["total_docs"] for r in data)
    total_changes = sum(r["docs_with_changes"] for r in data)
    overall = round(100.0 * (total_docs - total_changes) / total_docs, 2) if total_docs > 0 else 0
    return data, overall


def query_accuracy_field_level_trend(org_id: str, start_date: date, end_date: date, period: str = "week") -> tuple[list[dict], float]:
    from app.routers.accuracy import build_base_ctes
    date_trunc = "DATE_TRUNC('week', created_at)" if period == "week" else "DATE_TRUNC('day', created_at)"
    base_ctes = build_base_ctes(start_date, end_date, "", org_id)
    query = f"""
        WITH {base_ctes},
        field_accuracy_by_date AS (
            SELECT {date_trunc}::date as date, supplier_id, record_type, field_identifier, COUNT(*) as total_docs, SUM(is_accurate) as accurate_docs
            FROM comparisons GROUP BY 1, 2, 3, 4 HAVING COUNT(*) > 10
        )
        SELECT date, supplier_id, SUM(accurate_docs) as total_accurate, SUM(total_docs) as total_docs,
               ROUND(100.0 * SUM(accurate_docs) / NULLIF(SUM(total_docs), 0), 2) as accuracy_pct,
               SUM(total_docs) - SUM(accurate_docs) as docs_with_changes
        FROM field_accuracy_by_date WHERE date < DATE_TRUNC('week', CURRENT_DATE) GROUP BY 1, 2 ORDER BY 1, 2
    """
    rows = execute_query(query)
    data = [{"date": r["date"], "accuracy_pct": float(r["accuracy_pct"] or 0), "total_docs": r["total_docs"], "docs_with_changes": r["docs_with_changes"], "supplier_id": r.get("supplier_id")} for r in rows]
    total_docs = sum(r["total_docs"] for r in data)
    total_changes = sum(r["docs_with_changes"] for r in data)
    overall = round(100.0 * (total_docs - total_changes) / total_docs, 2) if total_docs > 0 else 0
    return data, overall
