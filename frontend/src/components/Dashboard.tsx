import React, { useState, useEffect } from 'react';
import { subDays } from 'date-fns';
import type { FilterState } from '../types';
import { useSuppliers, useSupplierOrganizations, useAiEnabledCount } from '../hooks/useMetrics';
import { FilterBar } from './FilterBar';
import { VolumeMetrics } from './VolumeMetrics';
import { CycleTimeMetrics } from './CycleTimeMetrics';
import { ProductivityMetrics } from './ProductivityMetrics';
import { AccuracyMetrics } from './AccuracyMetrics';
import { VpnReminderBanner } from './VpnReminderBanner';

// Check if running in static data mode
const STATIC_MODE = import.meta.env.VITE_STATIC_DATA === 'true';
// External sharing build: hide Accuracy card (not ready for external use)
const EXTERNAL_SHARING = import.meta.env.VITE_EXTERNAL_SHARING === 'true';

export const Dashboard: React.FC = () => {
  const [filters, setFilters] = useState<FilterState>({
    startDate: subDays(new Date(), 30),
    endDate: new Date(),
    aiIntakeOnly: true,
    supplierId: null,
    supplierOrganizationId: null,
  });

  // In static mode, default date range to exported data so graphs show data immediately
  useEffect(() => {
    if (!STATIC_MODE) return;
    fetch('/data/metadata.json')
      .then((r) => r.ok ? r.json() : null)
      .then((meta: { date_range?: { start_date?: string; end_date?: string } } | null) => {
        const start = meta?.date_range?.start_date;
        const end = meta?.date_range?.end_date;
        if (start && end) {
          try {
            const startDate = new Date(start + 'T00:00:00');
            const endDate = new Date(end + 'T00:00:00');
            if (!isNaN(startDate.getTime()) && !isNaN(endDate.getTime())) {
              setFilters((prev) => ({ ...prev, startDate, endDate }));
            }
          } catch (_) {
            // keep default range
          }
        }
      })
      .catch(() => {});
  }, []);

  const { data: suppliersData, isLoading: suppliersLoading } = useSuppliers(
    filters.aiIntakeOnly,
    undefined,
    filters.supplierOrganizationId
  );
  const { data: organizationsData, isLoading: organizationsLoading } = useSupplierOrganizations(
    filters.aiIntakeOnly
  );
  const { data: aiCountData } = useAiEnabledCount();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* VPN Reminder Banner - only show in non-static mode */}
      {!STATIC_MODE && <VpnReminderBanner />}
      
      {/* Header - only show in non-static mode */}
      {!STATIC_MODE && (
        <header className="bg-white shadow-sm border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  Intake Dashboard
                </h1>
                <p className="text-sm text-gray-500 mt-1">
                  Base Metrics → Business Insights
                </p>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="text-sm text-gray-500">AI Enabled Suppliers</p>
                  <p className="text-xl font-semibold text-blue-600">
                    {aiCountData?.ai_enabled_count || '-'}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </header>
      )}

      {/* Main Content */}
      <main className="w-full px-4 sm:px-6 lg:px-8 py-6">
        {/* Filters */}
        <FilterBar
          filters={filters}
          onFilterChange={setFilters}
          suppliers={suppliersData?.data || []}
          isLoadingSuppliers={suppliersLoading}
          organizations={organizationsData?.data || []}
          isLoadingOrganizations={organizationsLoading}
        />

        {/* Metrics Grid: 3 columns in external sharing (no Accuracy), 4 otherwise */}
        <div className={`grid grid-cols-1 md:grid-cols-2 gap-6 ${EXTERNAL_SHARING ? 'xl:grid-cols-3' : 'xl:grid-cols-4'}`}>
          {/* Volume - Green */}
          <VolumeMetrics filters={filters} />

          {/* Productivity - Fuchsia/Pink */}
          <ProductivityMetrics filters={filters} />

          {/* Cycle Time - Red */}
          <CycleTimeMetrics filters={filters} />

          {/* Accuracy - Blue (hidden in external sharing build) */}
          {!EXTERNAL_SHARING && <AccuracyMetrics filters={filters} />}
        </div>

        {/* Footer */}
        <footer className="mt-8 text-center text-sm text-gray-500">
          <p>
            Data sourced from Redshift • Last updated: {new Date().toLocaleString()}
          </p>
        </footer>
      </main>
    </div>
  );
};
