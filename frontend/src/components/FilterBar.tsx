import React from 'react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import type { FilterState, Supplier, SupplierOrganization } from '../types';

interface FilterBarProps {
  filters: FilterState;
  onFilterChange: (filters: FilterState) => void;
  suppliers: Supplier[];
  isLoadingSuppliers: boolean;
  organizations: SupplierOrganization[];
  isLoadingOrganizations: boolean;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  filters,
  onFilterChange,
  suppliers,
  isLoadingSuppliers,
  organizations,
  isLoadingOrganizations,
}) => {
  const handleDateChange = (field: 'startDate' | 'endDate', date: Date | null) => {
    if (date) {
      onFilterChange({ ...filters, [field]: date });
    }
  };

  const handleAiToggle = () => {
    onFilterChange({ ...filters, aiIntakeOnly: !filters.aiIntakeOnly });
  };

  const handleOrganizationChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    onFilterChange({ 
      ...filters, 
      supplierOrganizationId: value || null,
      supplierId: null  // Clear supplier filter when org is selected
    });
  };

  const handleSupplierChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    onFilterChange({ 
      ...filters, 
      supplierId: value || null,
      supplierOrganizationId: null  // Clear organization filter when supplier is selected
    });
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
      <div className="flex flex-wrap items-center gap-4">
        {/* Date Range */}
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">Date Range:</label>
          <DatePicker
            selected={filters.startDate}
            onChange={(date) => handleDateChange('startDate', date)}
            selectsStart
            startDate={filters.startDate}
            endDate={filters.endDate}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            dateFormat="MMM d, yyyy"
          />
          <span className="text-gray-500">to</span>
          <DatePicker
            selected={filters.endDate}
            onChange={(date) => handleDateChange('endDate', date)}
            selectsEnd
            startDate={filters.startDate}
            endDate={filters.endDate}
            minDate={filters.startDate}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            dateFormat="MMM d, yyyy"
          />
        </div>

        {/* AI Intake Toggle */}
        <div className="flex items-center gap-2">
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={filters.aiIntakeOnly}
              onChange={handleAiToggle}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            <span className="ms-3 text-sm font-medium text-gray-700">
              AI Intake Enabled Only
            </span>
          </label>
        </div>

        {/* Organization Filter */}
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">Organization:</label>
          <select
            value={filters.supplierOrganizationId || ''}
            onChange={handleOrganizationChange}
            disabled={isLoadingOrganizations}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-w-[200px]"
          >
            <option value="">All Organizations</option>
            {organizations.map((org) => (
              <option key={org.organization_id} value={org.organization_id}>
                {org.name} ({org.num_suppliers} suppliers)
              </option>
            ))}
          </select>
        </div>

        {/* Supplier Filter */}
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">Supplier:</label>
          <select
            value={filters.supplierId || ''}
            onChange={handleSupplierChange}
            disabled={isLoadingSuppliers}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-w-[200px]"
          >
            <option value="">All Suppliers</option>
            {suppliers.map((supplier) => (
              <option key={supplier.supplier_id} value={supplier.supplier_id}>
                {supplier.name} {supplier.ai_intake_enabled ? '(AI)' : ''}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
};
