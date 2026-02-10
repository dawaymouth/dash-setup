#!/usr/bin/env python3
"""
Export the full AI Intake dashboard: all AI intake-enabled supplier organizations.
Uses direct DB (no API): all metrics via bulk queries only; no per-org DB loop.
Output: minified JSON, rounded numbers, gzipped dashboard-data.json.gz + metadata.json for Vercel.
"""
import sys
import os
import json
import gzip
import argparse
import time
from datetime import datetime, timedelta, date
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(__file__))

from app.database import execute_query
from app import export_queries as eq

ALL_ORGS_ID = "__all__"
ALL_ORGS_NAME = "All Supplier Orgs"


def is_retryable_redshift_error(exc: BaseException) -> bool:
    """True if the exception looks like a transient Redshift 'could not open relation' (XX000) error."""
    msg = str(exc).lower()
    return "could not open relation" in msg or "xx000" in msg


def list_ai_intake_organizations():
    """Fetch only supplier organizations that have AI intake enabled."""
    query = """
        SELECT DISTINCT
            id.supplier_organization_id,
            id.supplier_organization as name,
            COUNT(DISTINCT id.supplier_id) as num_suppliers,
            COUNT(*) as total_faxes
        FROM analytics.intake_documents id
        WHERE id.supplier_organization_id IS NOT NULL
        GROUP BY id.supplier_organization_id, id.supplier_organization
        HAVING MAX(CASE WHEN id.is_ai_intake_enabled = true THEN 1 ELSE 0 END) = 1
        ORDER BY name
        LIMIT 500
    """
    return execute_query(query)


def get_suppliers_in_org(supplier_org_id):
    """List suppliers in the organization (direct DB)."""
    query = f"""
        SELECT DISTINCT
            id.supplier_id,
            id.supplier as name,
            MAX(CASE WHEN id.is_ai_intake_enabled = true THEN 1 ELSE 0 END)::boolean as ai_intake_enabled
        FROM analytics.intake_documents id
        WHERE id.supplier_organization_id = '{supplier_org_id}'
          AND id.supplier_id IS NOT NULL
        GROUP BY id.supplier_id, id.supplier
        ORDER BY name
    """
    rows = execute_query(query)
    return [{"supplier_id": r["supplier_id"], "name": r["name"], "ai_intake_enabled": r["ai_intake_enabled"]} for r in rows]


def round_numbers_with_keys(obj, parent_key=""):
    """Recursively round floats based on key names."""
    if isinstance(obj, dict):
        return {k: round_numbers_with_keys(v, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_numbers_with_keys(v, parent_key) for v in obj]
    if isinstance(obj, float):
        key_lower = (parent_key or "").lower()
        if "percentage" in key_lower or "accuracy_pct" in key_lower or "pct" in key_lower:
            return round(obj, 1)
        if any(x in key_lower for x in ("avg_minutes", "avg_per_day", "median_minutes", "avg_pages")):
            return round(obj, 2)
        return round(obj, 2)
    return obj


# ---------------------------------------------------------------------------
# Group bulk results by org_id (same shape as API for frontend)
# ---------------------------------------------------------------------------

def group_volume_by_org(rows):
    """Group volume bulk rows into by_org[org_id] = list of { date, count, supplier_id }."""
    by_org = {}
    for r in rows:
        oid = r.get("supplier_organization_id")
        if oid not in by_org:
            by_org[oid] = []
        by_org[oid].append({"date": str(r["date"]), "count": r["count"], "supplier_id": r.get("supplier_id")})
    return by_org


def group_categories_by_org(rows):
    """Group categories bulk rows; compute percentage per org. Shape: list of { category, count, percentage, supplier_id }."""
    by_org = {}
    for r in rows:
        oid = r.get("supplier_organization_id")
        if oid not in by_org:
            by_org[oid] = []
        by_org[oid].append({"category": r["category"], "count": r["count"], "supplier_id": r.get("supplier_id")})
    for oid in by_org:
        total = sum(x["count"] for x in by_org[oid])
        for x in by_org[oid]:
            x["percentage"] = round(x["count"] * 100.0 / total, 2) if total > 0 else 0
    return by_org


def group_time_of_day_by_org(rows):
    """Group time_of_day bulk rows into by_org[org_id] = list of { timestamp, supplier_id } (API shape)."""
    by_org = {}
    for r in rows:
        oid = r.get("supplier_organization_id")
        if oid not in by_org:
            by_org[oid] = []
        ts = r.get("document_created_at")
        by_org[oid].append({"timestamp": str(ts) if ts else None, "supplier_id": r.get("supplier_id")})
    return by_org


def group_suppliers_by_org(rows):
    """Group suppliers bulk rows into by_org[org_id] = list of { supplier_id, name, ai_intake_enabled }."""
    by_org = {}
    for r in rows:
        oid = r.get("supplier_organization_id")
        if oid not in by_org:
            by_org[oid] = []
        by_org[oid].append({"supplier_id": r["supplier_id"], "name": r["name"], "ai_intake_enabled": r["ai_intake_enabled"]})
    return by_org


def group_pages_org_by_org(rows):
    """Group pages org bulk into by_org[org_id] = { total_documents, total_pages }."""
    by_org = {}
    for r in rows:
        oid = r["supplier_organization_id"]
        by_org[oid] = {"total_documents": r["total_documents"] or 0, "total_pages": int(r["total_pages"] or 0)}
    return by_org


def group_pages_by_supplier_by_org(rows):
    """Group pages-by-supplier bulk into by_org[org_id] = list of { supplier_id, total_documents, total_pages }."""
    by_org = {}
    for r in rows:
        oid = r["supplier_organization_id"]
        if oid not in by_org:
            by_org[oid] = []
        by_org[oid].append({"supplier_id": r["supplier_id"], "total_documents": r.get("total_documents") or 0, "total_pages": int(r.get("total_pages") or 0)})
    return by_org


def group_doc_accuracy_by_supplier_by_org(rows):
    """Group document accuracy by supplier bulk into by_org[org_id] = list of { supplier_id, total_ai_docs, ... }."""
    by_org = {}
    for r in rows:
        oid = r["supplier_organization_id"]
        if oid not in by_org:
            by_org[oid] = []
        by_org[oid].append({"supplier_id": r["supplier_id"], "total_ai_docs": r["total_ai_docs"], "docs_with_edits": r["docs_with_edits"], "docs_no_edits": r["docs_no_edits"], "accuracy_pct": r["accuracy_pct"]})
    return by_org


def group_cycle_data_by_org(rows):
    """Group cycle data rows (with supplier_organization_id) into by_org[oid] = list of { date, supplier_id, avg_minutes, count }."""
    by_org = {}
    for r in rows:
        oid = r.get("supplier_organization_id")
        if oid is None:
            continue
        if oid not in by_org:
            by_org[oid] = []
        by_org[oid].append({"date": r.get("date"), "supplier_id": r.get("supplier_id"), "avg_minutes": r.get("avg_minutes"), "count": r.get("count")})
    return by_org


def group_cycle_state_distribution_by_org(rows):
    """Aggregate state distribution bulk rows per org into by_org[oid] = { data: [...], total } (same shape as per-org)."""
    STATE_LABELS = eq.STATE_LABELS
    by_org = {}
    for r in rows:
        oid = r["supplier_organization_id"]
        st = r["state"]
        cnt = r["count"]
        if oid not in by_org:
            by_org[oid] = {}
        by_org[oid][st] = by_org[oid].get(st, 0) + cnt
    result = {}
    for oid, state_totals in by_org.items():
        total = sum(state_totals.values())
        data = [{"state": st, "label": STATE_LABELS.get(st, st.title()), "count": c, "percentage": round(c * 100.0 / total, 2) if total > 0 else 0} for st, c in sorted(state_totals.items(), key=lambda x: -x[1])]
        result[oid] = {"data": data, "total": total}
    return result


def group_productivity_by_org(rows):
    """Group productivity bulk rows (with supplier_organization_id) into by_org[oid] = list of dicts (omit org_id in each row)."""
    by_org = {}
    for r in rows:
        oid = r.get("supplier_organization_id")
        if oid is None:
            continue
        if oid not in by_org:
            by_org[oid] = []
        copy = {k: v for k, v in r.items() if k != "supplier_organization_id"}
        by_org[oid].append(copy)
    return by_org


def group_accuracy_data_by_org(rows):
    """Group accuracy data rows (with supplier_organization_id) into by_org[oid] = list (omit org_id in each row)."""
    by_org = {}
    for r in rows:
        oid = r.get("supplier_organization_id")
        if oid is None:
            continue
        if oid not in by_org:
            by_org[oid] = []
        copy = {k: v for k, v in r.items() if k != "supplier_organization_id"}
        by_org[oid].append(copy)
    return by_org


# ---------------------------------------------------------------------------
# Merge helpers: aggregate *_by_org into single "all orgs" inputs
# ---------------------------------------------------------------------------

def _merge_volume_all(volume_by_org, org_ids):
    """Flatten volume across orgs, aggregate by date (sum count). Returns list of { date, count }."""
    from collections import defaultdict
    by_date = defaultdict(int)
    for oid in org_ids:
        for row in volume_by_org.get(oid, []):
            d = str(row.get("date") or "")
            by_date[d] += int(row.get("count") or 0)
    return [{"date": d, "count": c} for d, c in sorted(by_date.items())]


def _merge_categories_all(categories_by_org, org_ids):
    """Flatten categories across orgs, aggregate by category, recompute percentage."""
    from collections import defaultdict
    by_cat = defaultdict(int)
    for oid in org_ids:
        for row in categories_by_org.get(oid, []):
            c = row.get("category") or "Uncategorized"
            by_cat[c] += int(row.get("count") or 0)
    total = sum(by_cat.values())
    return [{"category": c, "count": cnt, "percentage": round(cnt * 100.0 / total, 2) if total > 0 else 0} for c, cnt in sorted(by_cat.items(), key=lambda x: -x[1])]


def _merge_time_of_day_all(time_of_day_by_org, org_ids):
    """Concatenate time_of_day lists across orgs."""
    out = []
    for oid in org_ids:
        out.extend(time_of_day_by_org.get(oid, []))
    return out


def _merge_suppliers_all(suppliers_by_org, org_ids):
    """Concatenate supplier lists, dedupe by supplier_id (keep first)."""
    seen = {}
    for oid in org_ids:
        for s in suppliers_by_org.get(oid, []):
            sid = s.get("supplier_id")
            if sid is not None and sid not in seen:
                seen[sid] = {"supplier_id": sid, "name": s.get("name"), "ai_intake_enabled": s.get("ai_intake_enabled")}
    return list(seen.values())


def _merge_pages_org_all(pages_org_by_org, org_ids):
    """Sum total_documents and total_pages across orgs."""
    total_docs = total_pages = 0
    for oid in org_ids:
        p = pages_org_by_org.get(oid)
        if p:
            total_docs += int(p.get("total_documents") or 0)
            total_pages += int(p.get("total_pages") or 0)
    return {"total_documents": total_docs, "total_pages": total_pages}


def _merge_pages_by_supplier_all(pages_by_supplier_by_org, org_ids):
    """Flatten pages-by-supplier, aggregate by supplier_id (sum)."""
    from collections import defaultdict
    by_sid = defaultdict(lambda: {"total_documents": 0, "total_pages": 0})
    for oid in org_ids:
        for row in pages_by_supplier_by_org.get(oid, []):
            sid = row.get("supplier_id")
            if sid is None:
                continue
            by_sid[sid]["total_documents"] += int(row.get("total_documents") or 0)
            by_sid[sid]["total_pages"] += int(row.get("total_pages") or 0)
    return [{"supplier_id": sid, "total_documents": v["total_documents"], "total_pages": v["total_pages"]} for sid, v in by_sid.items()]


def _merge_doc_accuracy_all(doc_accuracy_by_org, org_ids):
    """Flatten doc accuracy by supplier, aggregate by supplier_id; recompute accuracy_pct."""
    from collections import defaultdict
    by_sid = defaultdict(lambda: {"total_ai_docs": 0, "docs_with_edits": 0, "docs_no_edits": 0})
    for oid in org_ids:
        for row in doc_accuracy_by_org.get(oid, []):
            sid = row.get("supplier_id")
            if sid is None:
                continue
            by_sid[sid]["total_ai_docs"] += int(row.get("total_ai_docs") or 0)
            by_sid[sid]["docs_with_edits"] += int(row.get("docs_with_edits") or 0)
            by_sid[sid]["docs_no_edits"] += int(row.get("docs_no_edits") or 0)
    out = []
    for sid, v in by_sid.items():
        total = v["total_ai_docs"]
        pct = round(100.0 * v["docs_no_edits"] / total, 2) if total > 0 else 0
        out.append({"supplier_id": sid, "total_ai_docs": total, "docs_with_edits": v["docs_with_edits"], "docs_no_edits": v["docs_no_edits"], "accuracy_pct": pct})
    return out


def _merge_cycle_data_all(cycle_data_by_org, org_ids):
    """Flatten cycle data; return (data_list, overall_avg_minutes) with weighted average."""
    data = []
    for oid in org_ids:
        data.extend(cycle_data_by_org.get(oid, []))
    if not data:
        return [], 0
    total_count = 0
    weighted_sum = 0
    for row in data:
        c = int(row.get("count") or 0)
        avg = float(row.get("avg_minutes") or 0)
        total_count += c
        weighted_sum += avg * c
    overall = weighted_sum / total_count if total_count > 0 else 0
    return data, overall


def _merge_cycle_state_all(cycle_state_by_org, org_ids):
    """Sum state counts across orgs; build { data: [...], total } with labels and percentage."""
    STATE_LABELS = eq.STATE_LABELS
    by_state = {}
    for oid in org_ids:
        dist = cycle_state_by_org.get(oid)
        if not dist:
            continue
        for item in (dist.get("data") or []):
            st = item.get("state")
            if st is not None:
                by_state[st] = by_state.get(st, 0) + int(item.get("count") or 0)
    total = sum(by_state.values())
    data = [{"state": st, "label": STATE_LABELS.get(st, st.title() if st else ""), "count": c, "percentage": round(c * 100.0 / total, 2) if total > 0 else 0} for st, c in sorted(by_state.items(), key=lambda x: -x[1])]
    return {"data": data, "total": total}


def _merge_productivity_all(prod_by_org, org_ids):
    """Flatten productivity list across orgs (simplest: no aggregation by user_id)."""
    out = []
    for oid in org_ids:
        out.extend(prod_by_org.get(oid, []))
    return out


def _merge_acc_per_field_all(acc_per_field_by_org, org_ids):
    """Aggregate per_field by (record_type, field_identifier): sum total_docs, accurate_docs; recompute accuracy_pct."""
    from collections import defaultdict
    key_to_counts = defaultdict(lambda: {"total_docs": 0, "accurate_docs": 0})
    for oid in org_ids:
        for row in acc_per_field_by_org.get(oid, []):
            key = (row.get("record_type"), row.get("field_identifier"))
            key_to_counts[key]["total_docs"] += int(row.get("total_docs") or 0)
            key_to_counts[key]["accurate_docs"] += int(row.get("accurate_docs") or 0)
    out = []
    for (record_type, field_identifier), v in key_to_counts.items():
        total = v["total_docs"]
        pct = round(100.0 * v["accurate_docs"] / total, 2) if total > 0 else 0
        out.append({"record_type": record_type, "field_identifier": field_identifier, "total_docs": total, "accurate_docs": v["accurate_docs"], "accuracy_pct": pct})
    return out


def _merge_acc_per_field_overall_all(acc_per_field_by_org, org_ids):
    """Overall accuracy from merged per_field: sum accurate_docs / sum total_docs."""
    total_docs = total_acc = 0
    for oid in org_ids:
        for row in acc_per_field_by_org.get(oid, []):
            total_docs += int(row.get("total_docs") or 0)
            total_acc += int(row.get("accurate_docs") or 0)
    return round(100.0 * total_acc / total_docs, 2) if total_docs > 0 else 0


def _merge_acc_doc_all(acc_doc_by_org, org_ids):
    """Sum document-level totals across orgs; recompute accuracy_pct."""
    total_ai = docs_edits = docs_no_edits = 0
    for oid in org_ids:
        d = acc_doc_by_org.get(oid)
        if not d:
            continue
        total_ai += int(d.get("total_ai_docs") or 0)
        docs_edits += int(d.get("docs_with_edits") or 0)
        docs_no_edits += int(d.get("docs_no_edits") or 0)
    pct = round(100.0 * docs_no_edits / total_ai, 2) if total_ai > 0 else 0
    return {"total_ai_docs": total_ai, "docs_with_edits": docs_edits, "docs_no_edits": docs_no_edits, "accuracy_pct": pct}


def _merge_acc_trend_all(acc_trend_by_org, org_ids):
    """Aggregate trend by date: sum total_docs, docs_with_changes; recompute accuracy_pct per date."""
    from collections import defaultdict
    by_date = defaultdict(lambda: {"total_docs": 0, "docs_with_changes": 0})
    for oid in org_ids:
        for row in acc_trend_by_org.get(oid, []):
            d = str(row.get("date") or "")
            by_date[d]["total_docs"] += int(row.get("total_docs") or 0)
            by_date[d]["docs_with_changes"] += int(row.get("docs_with_changes") or 0)
    out = []
    for d in sorted(by_date.keys()):
        v = by_date[d]
        total = v["total_docs"]
        pct = round(100.0 * (total - v["docs_with_changes"]) / total, 2) if total > 0 else 0
        out.append({"date": d, "total_docs": total, "docs_with_changes": v["docs_with_changes"], "accuracy_pct": pct})
    return out


def _merge_acc_trend_overall_all(acc_trend_by_org, org_ids):
    """Overall trend accuracy: (sum total_docs - sum docs_with_changes) / sum total_docs."""
    total_docs = total_changes = 0
    for oid in org_ids:
        for row in acc_trend_by_org.get(oid, []):
            total_docs += int(row.get("total_docs") or 0)
            total_changes += int(row.get("docs_with_changes") or 0)
    return round(100.0 * (total_docs - total_changes) / total_docs, 2) if total_docs > 0 else 0


def assemble_one_org_from_bulk(
    oid, org_name,
    volume_list, categories_list, time_of_day_list,
    suppliers_list, pages_org, pages_by_supplier_list, doc_accuracy_list,
    cycle_recv_data, cycle_recv_overall, cycle_proc_data, cycle_proc_overall, cycle_state_dist,
    prod_by_ind, prod_daily, prod_proc_time, prod_cat,
    acc_per_field_list, acc_per_field_overall, acc_doc_org, acc_trend_list, acc_trend_overall, acc_field_trend_list, acc_field_trend_overall,
):
    """Build one org's export payload from pre-grouped bulk data (no DB). Same shape as export_one_org_db."""
    per_supplier = {}
    for row in pages_by_supplier_list or []:
        sid = row["supplier_id"]
        per_supplier[sid] = {"pages": {"total_documents": row.get("total_documents", 0), "total_pages": row.get("total_pages", 0)}, "document_accuracy": {}}
    for row in doc_accuracy_list or []:
        sid = row["supplier_id"]
        if sid not in per_supplier:
            per_supplier[sid] = {"pages": {}, "document_accuracy": {}}
        per_supplier[sid]["document_accuracy"] = {"total_ai_docs": row["total_ai_docs"], "docs_with_edits": row["docs_with_edits"], "docs_no_edits": row["docs_no_edits"], "accuracy_pct": row["accuracy_pct"]}
    for s in suppliers_list or []:
        sid = s["supplier_id"]
        if sid not in per_supplier:
            per_supplier[sid] = {"pages": {}, "document_accuracy": {}}

    cycle_time = {
        "received_to_open": {"data": cycle_recv_data or [], "overall_avg_minutes": cycle_recv_overall or 0, "metric_type": "received_to_open"},
        "processing": {"data": cycle_proc_data or [], "overall_avg_minutes": cycle_proc_overall or 0, "metric_type": "processing"},
        "state_distribution": cycle_state_dist or {"data": [], "total": 0},
    }
    productivity = {
        "by_individual": {"data": prod_by_ind or []},
        "daily_average": {"data": prod_daily or []},
        "by_individual_processing_time": {"data": prod_proc_time or []},
        "category_breakdown": {"data": prod_cat or []},
    }
    acc_per_field_list = acc_per_field_list or []
    accuracy = {
        "per_field": {"data": acc_per_field_list, "overall_accuracy_pct": acc_per_field_overall or 0, "total_fields": len(acc_per_field_list)},
        "document_level": acc_doc_org or {"total_ai_docs": 0, "docs_with_edits": 0, "docs_no_edits": 0, "accuracy_pct": 0},
        "trend": {"data": acc_trend_list or [], "overall_accuracy_pct": acc_trend_overall or 0, "period": "week"},
        "field_level_trend": {"data": acc_field_trend_list or [], "overall_accuracy_pct": acc_field_trend_overall or 0, "period": "week"},
    }
    organization = {
        "volume_by_day": volume_list or [],
        "categories": categories_list or [],
        "pages": pages_org or {"total_documents": 0, "total_pages": 0},
        "time_of_day": {"data": time_of_day_list or [], "total": len(time_of_day_list or [])},
        "cycle_time": cycle_time,
        "productivity": productivity,
        "accuracy": accuracy,
    }
    return {"organization": organization, "suppliers": suppliers_list or [], "per_supplier": per_supplier}


def export_one_org_db(org_id, org_name, start_date, end_date, volume_list, categories_list, time_of_day_list, org_index, total_orgs):
    """Export one org using direct DB (export_queries). Returns same shape as API export."""
    suppliers = get_suppliers_in_org(org_id)
    # Pages org-level
    pages = eq.query_pages_org(org_id, start_date, end_date)
    # Pages by supplier -> per_supplier[sid].pages
    pages_by_sup = eq.query_pages_by_supplier(org_id, start_date, end_date)
    per_supplier = {}
    for row in pages_by_sup:
        sid = row["supplier_id"]
        total_docs = row.get("total_documents") or 0
        total_pages = int(row.get("total_pages") or 0)
        per_supplier[sid] = {
            "pages": {"total_documents": total_docs, "total_pages": total_pages},
            "document_accuracy": {}
        }
    # Document accuracy by supplier
    doc_acc_by_sup = eq.query_document_accuracy_by_supplier(org_id, start_date, end_date)
    for row in doc_acc_by_sup:
        sid = row["supplier_id"]
        if sid not in per_supplier:
            per_supplier[sid] = {"pages": {}, "document_accuracy": {}}
        per_supplier[sid]["document_accuracy"] = {
            "total_ai_docs": row["total_ai_docs"],
            "docs_with_edits": row["docs_with_edits"],
            "docs_no_edits": row["docs_no_edits"],
            "accuracy_pct": row["accuracy_pct"]
        }
    # Ensure every supplier has an entry
    for s in suppliers:
        sid = s["supplier_id"]
        if sid not in per_supplier:
            per_supplier[sid] = {"pages": {}, "document_accuracy": {}}

    # Cycle time
    recv_data, recv_overall = eq.query_cycle_received_to_open(org_id, start_date, end_date)
    proc_data, proc_overall = eq.query_cycle_processing(org_id, start_date, end_date)
    state_dist = eq.query_cycle_state_distribution(org_id, start_date, end_date)
    cycle_time = {
        "received_to_open": {"data": recv_data, "overall_avg_minutes": recv_overall, "metric_type": "received_to_open"},
        "processing": {"data": proc_data, "overall_avg_minutes": proc_overall, "metric_type": "processing"},
        "state_distribution": state_dist
    }

    # Productivity
    prod_by_ind = eq.query_productivity_by_individual(org_id, start_date, end_date)
    prod_daily = eq.query_productivity_daily_average(org_id, start_date, end_date)
    prod_proc_time = eq.query_productivity_by_individual_processing_time(org_id, start_date, end_date)
    prod_cat = eq.query_productivity_category_breakdown(org_id, start_date, end_date)
    productivity = {
        "by_individual": {"data": prod_by_ind},
        "daily_average": {"data": prod_daily},
        "by_individual_processing_time": {"data": prod_proc_time},
        "category_breakdown": {"data": prod_cat}
    }

    # Accuracy
    acc_per_field, acc_overall = eq.query_accuracy_per_field(org_id, start_date, end_date)
    acc_doc_org = eq.query_accuracy_document_level_org(org_id, start_date, end_date)
    acc_trend_data, acc_trend_overall = eq.query_accuracy_trend(org_id, start_date, end_date, "week")
    acc_field_trend_data, acc_field_trend_overall = eq.query_accuracy_field_level_trend(org_id, start_date, end_date, "week")
    accuracy = {
        "per_field": {"data": acc_per_field, "overall_accuracy_pct": acc_overall, "total_fields": len(acc_per_field)},
        "document_level": acc_doc_org,
        "trend": {"data": acc_trend_data, "overall_accuracy_pct": acc_trend_overall, "period": "week"},
        "field_level_trend": {"data": acc_field_trend_data, "overall_accuracy_pct": acc_field_trend_overall, "period": "week"}
    }

    organization = {
        "volume_by_day": volume_list or [],
        "categories": categories_list or [],
        "pages": pages,
        "time_of_day": {"data": time_of_day_list or [], "total": len(time_of_day_list or [])},
        "cycle_time": cycle_time,
        "productivity": productivity,
        "accuracy": accuracy
    }
    return {
        "organization": organization,
        "suppliers": suppliers,
        "per_supplier": per_supplier,
    }


def main():
    parser = argparse.ArgumentParser(description="Export full AI Intake dashboard (all AI intake orgs) for Vercel.")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD (default: 90 days ago)")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory (default: frontend/public/data)")
    parser.add_argument("--workers", type=int, default=6, help="Parallel org workers (default: 6)")
    parser.add_argument("--no-parallel", action="store_true", help="Run orgs sequentially (no thread pool)")
    parser.add_argument("--check-backend", action="store_true", help="Require backend API to be running (default: not required)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of orgs (for testing)")
    args = parser.parse_args()

    end_date = date.today()
    if args.end:
        end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=90)
    if args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()

    print("=" * 60)
    print("Full AI Intake Dashboard Export (Direct DB)")
    print("=" * 60)
    print(f"\nDate range: {start_date} to {end_date}")

    if args.check_backend:
        print("\nChecking backend API...")
        try:
            import requests
            r = requests.get("http://localhost:8000/health", timeout=5)
            if r.status_code != 200:
                print("Backend not healthy.")
                sys.exit(1)
        except Exception as e:
            print(f"Cannot reach backend: {e}")
            sys.exit(1)
        print("Backend OK.")

    # 1. List AI intake orgs
    print("\nFetching AI intake organizations...")
    orgs = list_ai_intake_organizations()
    if not orgs:
        print("No AI intake organizations found.")
        sys.exit(1)
    org_ids = [o["supplier_organization_id"] for o in orgs]
    if args.limit:
        orgs = orgs[: args.limit]
        org_ids = org_ids[: args.limit]
        print(f"Limited to {len(orgs)} orgs (--limit {args.limit}).")
    print(f"Found {len(orgs)} AI intake organizations.")

    # 2. Bulk phase: all queries (no per-org DB)
    print("\nBulk queries (all metrics)...")
    volume_rows = eq.query_volume_by_day_bulk(start_date, end_date, org_ids)
    categories_rows = eq.query_categories_bulk(start_date, end_date, org_ids)
    time_of_day_rows = eq.query_time_of_day_bulk(start_date, end_date, org_ids)
    suppliers_rows = eq.query_suppliers_bulk(org_ids)
    pages_org_rows = eq.query_pages_org_bulk(start_date, end_date, org_ids)
    pages_by_supplier_rows = eq.query_pages_by_supplier_bulk(start_date, end_date, org_ids)
    doc_accuracy_rows = eq.query_document_accuracy_by_supplier_bulk(start_date, end_date, org_ids)
    cycle_recv_data, cycle_recv_overall = eq.query_cycle_received_to_open_bulk(start_date, end_date, org_ids)
    cycle_proc_data, cycle_proc_overall = eq.query_cycle_processing_bulk(start_date, end_date, org_ids)
    cycle_state_rows = eq.query_cycle_state_distribution_bulk(start_date, end_date, org_ids)
    prod_by_ind_rows = eq.query_productivity_by_individual_bulk(start_date, end_date, org_ids)
    prod_daily_rows = eq.query_productivity_daily_average_bulk(start_date, end_date, org_ids)
    prod_proc_time_rows = eq.query_productivity_by_individual_processing_time_bulk(start_date, end_date, org_ids)
    prod_cat_rows = eq.query_productivity_category_breakdown_bulk(start_date, end_date, org_ids)
    acc_per_field_data, acc_per_field_overall = eq.query_accuracy_per_field_bulk(start_date, end_date, org_ids)
    acc_doc_rows = eq.query_accuracy_document_level_org_bulk(start_date, end_date, org_ids)
    acc_trend_data, acc_trend_overall = eq.query_accuracy_trend_bulk(start_date, end_date, org_ids, "week")
    acc_field_trend_data, acc_field_trend_overall = eq.query_accuracy_field_level_trend_bulk(start_date, end_date, org_ids, "week")
    print("  Queries done. Grouping by org...")

    volume_by_org = group_volume_by_org(volume_rows)
    categories_by_org = group_categories_by_org(categories_rows)
    time_of_day_by_org = group_time_of_day_by_org(time_of_day_rows)
    suppliers_by_org = group_suppliers_by_org(suppliers_rows)
    pages_org_by_org = group_pages_org_by_org(pages_org_rows)
    pages_by_supplier_by_org = group_pages_by_supplier_by_org(pages_by_supplier_rows)
    doc_accuracy_by_org = group_doc_accuracy_by_supplier_by_org(doc_accuracy_rows)
    cycle_recv_by_org = group_cycle_data_by_org(cycle_recv_data)
    cycle_proc_by_org = group_cycle_data_by_org(cycle_proc_data)
    cycle_state_by_org = group_cycle_state_distribution_by_org(cycle_state_rows)
    prod_by_ind_by_org = group_productivity_by_org(prod_by_ind_rows)
    prod_daily_by_org = group_productivity_by_org(prod_daily_rows)
    prod_proc_time_by_org = group_productivity_by_org(prod_proc_time_rows)
    prod_cat_by_org = group_productivity_by_org(prod_cat_rows)
    acc_per_field_by_org = group_accuracy_data_by_org(acc_per_field_data)
    acc_doc_by_org = {}
    for r in acc_doc_rows:
        oid = r.get("supplier_organization_id")
        if oid is not None:
            acc_doc_by_org[oid] = {k: v for k, v in r.items() if k != "supplier_organization_id"}
    acc_trend_by_org = group_accuracy_data_by_org(acc_trend_data)
    acc_field_trend_by_org = group_accuracy_data_by_org(acc_field_trend_data)

    # 3. Assemble by_org from grouped bulk (no DB)
    print("  Assembling by org...")
    by_org = {}
    for org in orgs:
        oid = org["supplier_organization_id"]
        name = org["name"]
        by_org[oid] = assemble_one_org_from_bulk(
            oid, name,
            volume_by_org.get(oid, []),
            categories_by_org.get(oid, []),
            time_of_day_by_org.get(oid, []),
            suppliers_by_org.get(oid, []),
            pages_org_by_org.get(oid),
            pages_by_supplier_by_org.get(oid, []),
            doc_accuracy_by_org.get(oid, []),
            cycle_recv_by_org.get(oid, []),
            cycle_recv_overall.get(oid, 0),
            cycle_proc_by_org.get(oid, []),
            cycle_proc_overall.get(oid, 0),
            cycle_state_by_org.get(oid, {"data": [], "total": 0}),
            prod_by_ind_by_org.get(oid, []),
            prod_daily_by_org.get(oid, []),
            prod_proc_time_by_org.get(oid, []),
            prod_cat_by_org.get(oid, []),
            acc_per_field_by_org.get(oid, []),
            acc_per_field_overall.get(oid, 0),
            acc_doc_by_org.get(oid),
            acc_trend_by_org.get(oid, []),
            acc_trend_overall.get(oid, 0),
            acc_field_trend_by_org.get(oid, []),
            acc_field_trend_overall.get(oid, 0),
        )

    # 3b. Assemble "All Supplier Orgs" slice (aggregated across all orgs)
    print("  Assembling All Supplier Orgs...")
    merged_volume = _merge_volume_all(volume_by_org, org_ids)
    merged_categories = _merge_categories_all(categories_by_org, org_ids)
    merged_time_of_day = _merge_time_of_day_all(time_of_day_by_org, org_ids)
    merged_suppliers = _merge_suppliers_all(suppliers_by_org, org_ids)
    merged_pages_org = _merge_pages_org_all(pages_org_by_org, org_ids)
    merged_pages_by_supplier = _merge_pages_by_supplier_all(pages_by_supplier_by_org, org_ids)
    merged_doc_accuracy = _merge_doc_accuracy_all(doc_accuracy_by_org, org_ids)
    merged_cycle_recv_data, merged_cycle_recv_overall = _merge_cycle_data_all(cycle_recv_by_org, org_ids)
    merged_cycle_proc_data, merged_cycle_proc_overall = _merge_cycle_data_all(cycle_proc_by_org, org_ids)
    merged_cycle_state = _merge_cycle_state_all(cycle_state_by_org, org_ids)
    merged_prod_by_ind = _merge_productivity_all(prod_by_ind_by_org, org_ids)
    merged_prod_daily = _merge_productivity_all(prod_daily_by_org, org_ids)
    merged_prod_proc_time = _merge_productivity_all(prod_proc_time_by_org, org_ids)
    merged_prod_cat = _merge_productivity_all(prod_cat_by_org, org_ids)
    merged_acc_per_field = _merge_acc_per_field_all(acc_per_field_by_org, org_ids)
    merged_acc_per_field_overall = _merge_acc_per_field_overall_all(acc_per_field_by_org, org_ids)
    merged_acc_doc = _merge_acc_doc_all(acc_doc_by_org, org_ids)
    merged_acc_trend = _merge_acc_trend_all(acc_trend_by_org, org_ids)
    merged_acc_trend_overall = _merge_acc_trend_overall_all(acc_trend_by_org, org_ids)
    merged_acc_field_trend = _merge_acc_trend_all(acc_field_trend_by_org, org_ids)
    merged_acc_field_trend_overall = _merge_acc_trend_overall_all(acc_field_trend_by_org, org_ids)

    by_org[ALL_ORGS_ID] = assemble_one_org_from_bulk(
        ALL_ORGS_ID, ALL_ORGS_NAME,
        merged_volume,
        merged_categories,
        merged_time_of_day,
        merged_suppliers,
        merged_pages_org,
        merged_pages_by_supplier,
        merged_doc_accuracy,
        merged_cycle_recv_data,
        merged_cycle_recv_overall,
        merged_cycle_proc_data,
        merged_cycle_proc_overall,
        merged_cycle_state,
        merged_prod_by_ind,
        merged_prod_daily,
        merged_prod_proc_time,
        merged_prod_cat,
        merged_acc_per_field,
        merged_acc_per_field_overall,
        merged_acc_doc,
        merged_acc_trend,
        merged_acc_trend_overall,
        merged_acc_field_trend,
        merged_acc_field_trend_overall,
    )

    if not by_org:
        print("No organization data exported.")
        sys.exit(1)

    # 4. Round numbers
    print("\nRounding numbers...")
    payload = {"by_org": round_numbers_with_keys(by_org)}

    # 5. Metadata
    total_faxes = 0
    org_list = []
    for oid, data in by_org.items():
        if oid == ALL_ORGS_ID:
            continue
        org_record = next((o for o in orgs if o["supplier_organization_id"] == oid), None)
        name = org_record["name"] if org_record else oid
        num_suppliers = len(data.get("suppliers", []))
        faxes = sum(row.get("count", 0) for row in data.get("organization", {}).get("volume_by_day", []))
        total_faxes += faxes
        org_list.append({"id": oid, "name": name, "num_suppliers": num_suppliers})
    # Prepend "All Supplier Orgs" so it appears first (and can be default)
    org_list.insert(0, {"id": ALL_ORGS_ID, "name": ALL_ORGS_NAME, "num_suppliers": len(merged_suppliers)})

    metadata = {
        "organizations": org_list,
        "date_range": {"start_date": str(start_date), "end_date": str(end_date)},
        "exported_at": datetime.now().isoformat(),
        "total_faxes": total_faxes,
    }

    # 6. Output directory
    output_dir = Path(args.output_dir) if args.output_dir else Path(__file__).parent.parent / "frontend" / "public" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 7. Write files (minified + gzip)
    minify_kw = {"separators": (",", ":"), "default": str}
    print("\nWriting files...")
    metadata_path = output_dir / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, **minify_kw)
    print(f"  {metadata_path} ({metadata_path.stat().st_size / 1024:.1f} KB)")
    json_str = json.dumps(payload, **minify_kw)
    data_path = output_dir / "dashboard-data.json"
    with open(data_path, "w") as f:
        f.write(json_str)
    size_mb = len(json_str.encode("utf-8")) / (1024 * 1024)
    print(f"  {data_path} ({size_mb:.2f} MB)")
    gz_path = output_dir / "dashboard-data.json.gz"
    with gzip.open(gz_path, "wt", encoding="utf-8") as f:
        f.write(json_str)
    print(f"  {gz_path} ({gz_path.stat().st_size / (1024 * 1024):.2f} MB)")

    print("\n" + "=" * 60)
    print("Export complete")
    print("=" * 60)
    print(f"Organizations: {len(by_org)}")
    print(f"Total faxes: {total_faxes:,}")
    print(f"Output: {output_dir}")
    print("\nNext: build frontend with VITE_STATIC_DATA=true and deploy to Vercel.")


if __name__ == "__main__":
    main()
