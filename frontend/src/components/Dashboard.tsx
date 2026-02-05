import React, { useState } from 'react';
import { subDays } from 'date-fns';
import type { FilterState } from '../types';
import { useSuppliers, useSupplierOrganizations, useAiEnabledCount } from '../hooks/useMetrics';
import { FilterBar } from './FilterBar';
import { VolumeMetrics } from './VolumeMetrics';
import { CycleTimeMetrics } from './CycleTimeMetrics';
import { ProductivityMetrics } from './ProductivityMetrics';
import { AccuracyMetrics } from './AccuracyMetrics';

export const Dashboard: React.FC = () => {
  const [filters, setFilters] = useState<FilterState>({
    startDate: subDays(new Date(), 30),
    endDate: new Date(),
    aiIntakeOnly: true,
    supplierId: null,
    supplierOrganizationId: null,
  });

  const { data: suppliersData, isLoading: suppliersLoading } = useSuppliers(
    filters.aiIntakeOnly
  );
  const { data: organizationsData, isLoading: organizationsLoading } = useSupplierOrganizations(
    filters.aiIntakeOnly
  );
  const { data: aiCountData } = useAiEnabledCount();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
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

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          {/* Volume - Green */}
          <VolumeMetrics filters={filters} />

          {/* Productivity - Fuchsia/Pink */}
          <ProductivityMetrics filters={filters} />

          {/* Cycle Time - Red */}
          <CycleTimeMetrics filters={filters} />

          {/* Accuracy - Blue */}
          <AccuracyMetrics filters={filters} />
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
