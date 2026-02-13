#!/usr/bin/env python3
"""
Interactive tool to export dashboard data for external sharing.

Uses direct DB and bulk queries (same as full export). No API or backend required.

By default, each org's export goes to external-exports/<org-slug>/ so Cardinal and
Adapt Health (etc.) do not overwrite each other. Re-exporting the same org
overwrites only that org's directory. To build: ./scripts/build-external.sh
(or ./scripts/build-external.sh <org-slug>). Use --output-dir to override.
"""
import sys
import os
import re
import json
import argparse
from datetime import datetime, timedelta, date
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from app.database import execute_query
from app import export_queries as eq

# Reuse grouping and assembly from full export
from export_full_ai_dashboard import (
    group_volume_by_org,
    group_categories_by_org,
    group_time_of_day_by_org,
    group_suppliers_by_org,
    group_pages_org_by_org,
    group_pages_by_supplier_by_org,
    group_doc_accuracy_by_supplier_by_org,
    group_cycle_data_by_org,
    group_cycle_state_distribution_by_org,
    group_cycle_state_distribution_by_supplier,
    group_cycle_state_distribution_by_user,
    group_productivity_by_org,
    group_accuracy_data_by_org,
    assemble_one_org_from_bulk,
)


def org_name_to_slug(name: str) -> str:
    """Derive a stable slug from org name: lowercase, spaces to dashes, alphanumeric and dash only."""
    slug = (name or "").lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "export"


def list_supplier_organizations():
    """Fetch and display all supplier organizations."""
    query = """
        SELECT DISTINCT
            id.supplier_organization_id,
            id.supplier_organization as name,
            COUNT(DISTINCT id.supplier_id) as num_suppliers,
            MAX(CASE WHEN id.is_ai_intake_enabled = true THEN 1 ELSE 0 END)::boolean as has_ai_intake,
            COUNT(*) as total_faxes
        FROM analytics.intake_documents id
        WHERE id.supplier_organization_id IS NOT NULL
        GROUP BY id.supplier_organization_id, id.supplier_organization
        ORDER BY name
        LIMIT 500
    """
    results = execute_query(query)
    return results


def get_date_range_input():
    """Prompt user for date range."""
    print("\n📅 Date Range Options:")
    print("1. Last 30 days")
    print("2. Last 90 days (quarter)")
    print("3. Last 6 months")
    print("4. Year to date (2026)")
    print("5. Custom range")

    choice = input("\nSelect option (1-5): ").strip()

    end_date = date.today()

    if choice == "1":
        start_date = end_date - timedelta(days=30)
    elif choice == "2":
        start_date = end_date - timedelta(days=90)
    elif choice == "3":
        start_date = end_date - timedelta(days=180)
    elif choice == "4":
        start_date = date(2026, 1, 1)
    elif choice == "5":
        start_str = input("Enter start date (YYYY-MM-DD): ").strip()
        end_str = input("Enter end date (YYYY-MM-DD): ").strip()
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    else:
        print("Invalid choice. Using last 30 days.")
        start_date = end_date - timedelta(days=30)

    return start_date, end_date


def get_suppliers_in_org(supplier_org_id):
    """Get list of suppliers in the organization using direct DB query."""
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
    results = execute_query(query)
    return [
        {"supplier_id": row["supplier_id"], "name": row["name"], "ai_intake_enabled": row["ai_intake_enabled"]}
        for row in results
    ]


TREND_WINDOW_DAYS = 365


def export_one_org_via_bulk(supplier_org_id, org_name, start_date, end_date):
    """Export one org using direct DB bulk queries (same pattern as full export)."""
    org_ids = [supplier_org_id]

    # Trend data uses extended range (up to 365 days) so trend charts can show 30d–1yr
    trend_start = min(start_date, end_date - timedelta(days=TREND_WINDOW_DAYS))
    trend_end = end_date

    print("  📊 Bulk queries (one org)...")
    volume_rows = eq.query_volume_by_day_bulk(trend_start, trend_end, org_ids)
    categories_rows = eq.query_categories_bulk(start_date, end_date, org_ids)
    time_of_day_rows = eq.query_time_of_day_bulk(start_date, end_date, org_ids)
    suppliers_rows = eq.query_suppliers_bulk(org_ids)
    pages_org_rows = eq.query_pages_org_bulk(start_date, end_date, org_ids)
    pages_by_supplier_rows = eq.query_pages_by_supplier_bulk(start_date, end_date, org_ids)
    doc_accuracy_rows = eq.query_document_accuracy_by_supplier_bulk(start_date, end_date, org_ids)
    cycle_recv_data, cycle_recv_overall = eq.query_cycle_received_to_open_bulk(start_date, end_date, org_ids)
    recv_median_min = cycle_recv_overall.get(supplier_org_id, 0)
    print(f"  Median Received to Open (business hours): {recv_median_min:.0f} min")
    cycle_proc_data, cycle_proc_overall = eq.query_cycle_processing_bulk(start_date, end_date, org_ids)
    cycle_state_rows = eq.query_cycle_state_distribution_bulk(start_date, end_date, org_ids)
    cycle_state_by_user_rows = eq.query_cycle_state_distribution_by_user_bulk(start_date, end_date, org_ids)
    active_individuals_by_org = eq.query_active_individuals_bulk(start_date, end_date, org_ids)
    prod_by_ind_rows = eq.query_productivity_by_individual_bulk(start_date, end_date, org_ids)
    prod_daily_rows = eq.query_productivity_daily_average_bulk(start_date, end_date, org_ids)
    prod_proc_time_rows = eq.query_productivity_by_individual_processing_time_bulk(start_date, end_date, org_ids)
    prod_cat_rows = eq.query_productivity_category_breakdown_bulk(start_date, end_date, org_ids)
    acc_per_field_data, acc_per_field_overall = eq.query_accuracy_per_field_bulk(start_date, end_date, org_ids)
    acc_doc_rows = eq.query_accuracy_document_level_org_bulk(start_date, end_date, org_ids)
    acc_trend_data, acc_trend_overall = eq.query_accuracy_trend_bulk(trend_start, trend_end, org_ids, "week")
    acc_field_trend_data, acc_field_trend_overall = eq.query_accuracy_field_level_trend_bulk(
        trend_start, trend_end, org_ids, "week"
    )
    print("  Grouping and assembling...")

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
    cycle_state_by_supplier_by_org = group_cycle_state_distribution_by_supplier(cycle_state_rows)
    cycle_state_by_user_by_org = group_cycle_state_distribution_by_user(cycle_state_by_user_rows)

    unique_individuals = active_individuals_by_org.get(supplier_org_id, 0)
    slice_data = assemble_one_org_from_bulk(
        supplier_org_id,
        org_name,
        volume_by_org.get(supplier_org_id, []),
        categories_by_org.get(supplier_org_id, []),
        time_of_day_by_org.get(supplier_org_id, []),
        suppliers_by_org.get(supplier_org_id, []),
        pages_org_by_org.get(supplier_org_id),
        pages_by_supplier_by_org.get(supplier_org_id, []),
        doc_accuracy_by_org.get(supplier_org_id, []),
        cycle_recv_by_org.get(supplier_org_id, []),
        cycle_recv_overall.get(supplier_org_id, 0),
        cycle_proc_by_org.get(supplier_org_id, []),
        cycle_proc_overall.get(supplier_org_id, 0),
        cycle_state_by_org.get(supplier_org_id, {"data": [], "total": 0}),
        cycle_state_by_supplier_by_org.get(supplier_org_id, {}),
        cycle_state_by_user_by_org.get(supplier_org_id, {}),
        prod_by_ind_by_org.get(supplier_org_id, []),
        prod_daily_by_org.get(supplier_org_id, []),
        prod_proc_time_by_org.get(supplier_org_id, []),
        prod_cat_by_org.get(supplier_org_id, []),
        unique_individuals,
        acc_per_field_by_org.get(supplier_org_id, []),
        acc_per_field_overall.get(supplier_org_id, 0),
        acc_doc_by_org.get(supplier_org_id),
        acc_trend_by_org.get(supplier_org_id, []),
        acc_trend_overall.get(supplier_org_id, 0),
        acc_field_trend_by_org.get(supplier_org_id, []),
        acc_field_trend_overall.get(supplier_org_id, 0),
    )
    return slice_data


def main():
    """Main export flow."""
    parser = argparse.ArgumentParser(
        description="Export dashboard data for external sharing (single org). Use --output-dir to write to a dedicated directory for multiple exports."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to write metadata.json and dashboard-data.json (default: external-exports/<org-slug>/)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("🚀 External Dashboard Data Export Tool (Direct DB)")
    print("=" * 60)

    # Step 1: List and select supplier organization
    print("\n📋 Fetching supplier organizations...")
    orgs = list_supplier_organizations()

    if not orgs:
        print("❌ No supplier organizations found!")
        sys.exit(1)

    print(f"\n✅ Found {len(orgs)} supplier organizations:\n")
    for i, org in enumerate(orgs, 1):
        ai_status = "✓ AI Enabled" if org["has_ai_intake"] else "  No AI"
        print(f"{i:3d}. {org['name']:<40} ({org['num_suppliers']} suppliers, {org['total_faxes']:,} faxes) {ai_status}")

    while True:
        try:
            selection = int(input(f"\nSelect organization (1-{len(orgs)}): ").strip())
            if 1 <= selection <= len(orgs):
                selected_org = orgs[selection - 1]
                break
            print(f"Please enter a number between 1 and {len(orgs)}")
        except ValueError:
            print("Please enter a valid number")

    print(f"\n✅ Selected: {selected_org['name']} (ID: {selected_org['supplier_organization_id']})")

    # Step 2: Get date range
    start_date, end_date = get_date_range_input()
    print(f"✅ Date range: {start_date} to {end_date}")

    supplier_org_id = selected_org["supplier_organization_id"]
    org_name = selected_org["name"]

    try:
        # Step 3: Export via direct DB (no backend required)
        print("\n📥 Exporting data (direct DB, no API)...")
        slice_data = export_one_org_via_bulk(supplier_org_id, org_name, start_date, end_date)

        # Step 4: Create output directory (default: per-org under external-exports/)
        if args.output_dir:
            output_dir = Path(args.output_dir).resolve()
        else:
            slug = org_name_to_slug(org_name)
            proj_root = Path(__file__).parent.parent
            output_dir = proj_root / "external-exports" / slug
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 5: Write JSON files (legacy single-org shape for frontend)
        print("\n💾 Saving data files...")
        all_data = {
            "organization": slice_data["organization"],
            "suppliers": slice_data["suppliers"],
            "per_supplier": slice_data["per_supplier"],
        }

        suppliers_list = [
            {"id": sup["supplier_id"], "name": sup["name"], "ai_intake_enabled": sup["ai_intake_enabled"]}
            for sup in slice_data["suppliers"]
        ]
        # Total faxes = main range only (volume_by_day may contain extended trend data)
        volume_rows_main = [
            r for r in slice_data["organization"].get("volume_by_day", [])
            if str(start_date) <= str(r.get("date", "")) <= str(end_date)
        ]
        total_faxes = sum(row.get("count", 0) for row in volume_rows_main)

        metadata = {
            "supplier_organization": {
                "id": supplier_org_id,
                "name": org_name,
                "num_suppliers": len(suppliers_list),
            },
            "suppliers": suppliers_list,
            "date_range": {"start_date": str(start_date), "end_date": str(end_date)},
            "exported_at": datetime.now().isoformat(),
            "total_faxes": total_faxes,
        }

        with open(output_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2, default=str)
        with open(output_dir / "dashboard-data.json", "w") as f:
            json.dump(all_data, f, indent=2, default=str)

        for fname in ("metadata.json", "dashboard-data.json"):
            size_mb = (output_dir / fname).stat().st_size / (1024 * 1024)
            print(f"     • {fname} ({size_mb:.1f} MB)")

        print("\n" + "=" * 60)
        print("✅ Export Complete!")
        print("=" * 60)
        print(f"\nData exported for: {org_name}")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Total faxes: {metadata['total_faxes']:,}")
        print(f"Suppliers: {len(suppliers_list)}")
        print("\nNext steps:")
        if args.output_dir:
            try:
                proj_root = Path(__file__).parent.parent
                rel_dir = output_dir.relative_to(proj_root)
            except ValueError:
                rel_dir = output_dir
            print(f"  To build this export: ./scripts/build-external.sh {rel_dir}")
        else:
            slug = org_name_to_slug(org_name)
            print(f"  To build this export: ./scripts/build-external.sh {slug}")
            print("  (Or run ./scripts/build-external.sh and the latest export will be used)")
        print("2. Deploy to Vercel")
        print("3. Enable password protection in Vercel dashboard")
        print("4. Share URL + password with customer")

    except Exception as e:
        print(f"\n❌ Error exporting data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
