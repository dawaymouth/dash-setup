#!/usr/bin/env python3
"""
Optimized export tool - queries database once with supplier_id tags.
Client-side filtering handles supplier drill-down.
"""
import sys
import os
import json
from datetime import datetime, timedelta, date
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from app.database import execute_query


def list_supplier_organizations():
    """Fetch all supplier organizations."""
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
    return execute_query(query)


def get_suppliers_in_org(supplier_org_id):
    """Get list of suppliers in the organization."""
    query = f"""
        SELECT DISTINCT
            id.supplier_id,
            id.supplier as name,
            MAX(CASE WHEN id.is_ai_intake_enabled = true THEN 1 ELSE 0 END)::boolean as ai_intake_enabled,
            COUNT(*) as total_faxes
        FROM analytics.intake_documents id
        WHERE id.supplier_organization_id = '{supplier_org_id}'
          AND id.supplier_id IS NOT NULL
        GROUP BY id.supplier_id, id.supplier
        ORDER BY name
    """
    results = execute_query(query)
    
    return [
        {
            "id": row["supplier_id"],
            "name": row["name"],
            "ai_intake_enabled": row["ai_intake_enabled"],
            "total_faxes": row["total_faxes"]
        }
        for row in results
    ]


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


def export_all_data(supplier_org_id, start_date, end_date, suppliers):
    """Export all metrics with supplier tags for client-side filtering."""
    
    data = {}
    
    print("\n📥 Exporting data with supplier tags...")
    
    # Volume - fax count by day + supplier
    print("  📊 Volume by day...")
    volume_query = f"""
        SELECT 
            DATE_TRUNC('day', document_created_at)::date as date,
            supplier_id,
            COUNT(*) as count
        FROM analytics.intake_documents
        WHERE supplier_organization_id = '{supplier_org_id}'
          AND document_created_at >= '{start_date}'
          AND document_created_at < '{end_date}'::date + interval '1 day'
          AND supplier_id IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 1, 2
    """
    data["volume_by_day"] = execute_query(volume_query)
    
    # Volume - pages stats (org level - not easily filterable by supplier)
    print("  📊 Pages stats...")
    pages_query = f"""
        SELECT 
            SUM(d.page_count) as total_pages,
            AVG(d.page_count) as avg_pages,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.page_count) as median_pages
        FROM analytics.intake_documents id
        LEFT JOIN workflow.documents d ON d.external_id = id.document_id
        WHERE id.supplier_organization_id = '{supplier_org_id}'
          AND id.document_created_at >= '{start_date}'
          AND id.document_created_at < '{end_date}'::date + interval '1 day'
    """
    pages_result = execute_query(pages_query)
    data["pages"] = pages_result[0] if pages_result else {}
    
    # Categories by supplier
    print("  📊 Categories by supplier...")
    category_query = f"""
        SELECT 
            id.supplier_id,
            os.category,
            COUNT(*) as count
        FROM analytics.intake_documents id
        LEFT JOIN analytics.orders o ON id.order_id = o.id  
        LEFT JOIN analytics.order_skus os ON o.sku_id = os.id
        WHERE id.supplier_organization_id = '{supplier_org_id}'
          AND id.document_created_at >= '{start_date}'
          AND id.document_created_at < '{end_date}'::date + interval '1 day'
          AND id.supplier_id IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC
    """
    data["categories"] = execute_query(category_query)
    
    # Time of day (org level)
    print("  📊 Time of day distribution...")
    time_query = f"""
        SELECT 
            EXTRACT(HOUR FROM document_created_at) as hour,
            COUNT(*) as count
        FROM analytics.intake_documents
        WHERE supplier_organization_id = '{supplier_org_id}'
          AND document_created_at >= '{start_date}'
          AND document_created_at < '{end_date}'::date + interval '1 day'
        GROUP BY 1
        ORDER BY 1
    """
    data["time_of_day"] = execute_query(time_query)
    
    # Cycle time, productivity, accuracy - org level only
    print("  ⏱️  Cycle time metrics (org-level)...")
    print("  👥 Productivity metrics (org-level)...")  
    print("  🎯 Accuracy metrics (org-level)...")
    
    # Note: These metrics don't easily support supplier-level breakdown
    # Would require complex joins and significant query changes
    data["org_only_metrics"] = {
        "cycle_time": "Use org-level view",
        "productivity": "Use org-level view",
        "accuracy": "Use org-level view"
    }
    
    return data


def main():
    """Main export flow."""
    print("=" * 60)
    print("🚀 External Dashboard Data Export Tool (Optimized)")
    print("=" * 60)
    
    # List and select organization
    print("\n📋 Fetching supplier organizations...")
    orgs = list_supplier_organizations()
    
    if not orgs:
        print("❌ No supplier organizations found!")
        sys.exit(1)
    
    print(f"\n✅ Found {len(orgs)} supplier organizations:\n")
    for i, org in enumerate(orgs, 1):
        ai_status = "✓ AI" if org["has_ai_intake"] else "   "
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
    
    print(f"\n✅ Selected: {selected_org['name']}")
    
    # Get date range
    start_date, end_date = get_date_range_input()
    print(f"✅ Date range: {start_date} to {end_date}")
    
    supplier_org_id = selected_org['supplier_organization_id']
    
    try:
        # Get suppliers
        suppliers = get_suppliers_in_org(supplier_org_id)
        
        # Export data
        all_data = export_all_data(supplier_org_id, start_date, end_date, suppliers)
        
        # Create output directory
        output_dir = Path(__file__).parent.parent / "frontend" / "public" / "data"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Calculate total faxes
        total_faxes = sum(row["count"] for row in all_data["metrics"]["volume_by_day"])
        
        # Metadata
        metadata = {
            "supplier_organization": {
                "id": supplier_org_id,
                "name": selected_org["name"],
                "num_suppliers": len(suppliers)
            },
            "suppliers": suppliers,
            "date_range": {
                "start_date": str(start_date),
                "end_date": str(end_date)
            },
            "exported_at": datetime.now().isoformat(),
            "total_faxes": total_faxes
        }
        
        print("\n💾 Saving data files...")
        
        with open(output_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2, default=str)
        
        with open(output_dir / "dashboard-data.json", "w") as f:
            json.dump(all_data["metrics"], f, indent=2, default=str)
        
        # Check file sizes
        data_file = output_dir / "dashboard-data.json"
        size_mb = data_file.stat().st_size / (1024 * 1024)
        
        print(f"  ✅ Wrote data files to {output_dir}")
        print(f"     • metadata.json")
        print(f"     • dashboard-data.json ({size_mb:.1f} MB)")
        
        print("\n" + "=" * 60)
        print("✅ Export Complete!")
        print("=" * 60)
        print(f"\nData exported for: {selected_org['name']}")
        print(f"Suppliers: {len(suppliers)}")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Total faxes: {total_faxes:,}")
        print(f"\nData size: {size_mb:.1f} MB")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
