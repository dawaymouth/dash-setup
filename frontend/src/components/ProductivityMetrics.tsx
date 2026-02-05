import React, { useState, useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { FilterState } from '../types';
import {
  useProductivityByIndividual,
} from '../hooks/useMetrics';
import { Modal } from './Modal';
import { InfoButton } from './InfoButton';
import { ProductivityCalculations } from './calculationDocs';

interface ProductivityMetricsProps {
  filters: FilterState;
}

export const ProductivityMetrics: React.FC<ProductivityMetricsProps> = ({ filters }) => {
  const [view, setView] = useState<'total' | 'daily' | 'speed'>('total');
  const [showInfoModal, setShowInfoModal] = useState(false);
  
  // Fetch once with higher limit for more complete data
  const { data, isLoading } = useProductivityByIndividual(filters, 50);

  // Client-side sorting based on selected view
  const sortedData = useMemo(() => {
    if (!data?.data) return [];
    
    const sorted = [...data.data];
    
    if (view === 'total') {
      return sorted.sort((a, b) => b.total_processed - a.total_processed);
    } else if (view === 'daily') {
      return sorted.sort((a, b) => b.avg_per_day - a.avg_per_day);
    } else { // speed
      return sorted.sort((a, b) => {
        // Handle null values - push to end
        if (a.median_minutes === null) return 1;
        if (b.median_minutes === null) return -1;
        return a.median_minutes - b.median_minutes; // Ascending - fastest first
      });
    }
  }, [data, view]);

  // Prepare chart data - top 10 performers based on current sort
  const chartData = sortedData.slice(0, 10).map((item) => ({
    name: item.user_name.split(' ')[0], // First name only for chart
    fullName: item.user_name,
    value: view === 'total' 
      ? item.total_processed 
      : view === 'daily' 
      ? item.avg_per_day 
      : item.median_minutes || 0,
  }));

  return (
    <div className="bg-white rounded-lg shadow-sm border-l-4 border-l-fuchsia-500 border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800 flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-fuchsia-500"></div>
          Productivity
          <InfoButton onClick={() => setShowInfoModal(true)} />
        </h2>
        <div className="flex gap-2">
          <button
            onClick={() => setView('total')}
            className={`px-3 py-1 text-sm rounded-md transition-colors ${
              view === 'total'
                ? 'bg-fuchsia-500 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Total
          </button>
          <button
            onClick={() => setView('daily')}
            className={`px-3 py-1 text-sm rounded-md transition-colors ${
              view === 'daily'
                ? 'bg-fuchsia-500 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Daily Avg
          </button>
          <button
            onClick={() => setView('speed')}
            className={`px-3 py-1 text-sm rounded-md transition-colors ${
              view === 'speed'
                ? 'bg-fuchsia-500 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Speed
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-fuchsia-500"></div>
        </div>
      ) : (
        <>
          {/* Stats Cards */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="bg-fuchsia-50 rounded-lg p-4">
              <p className="text-sm text-fuchsia-600 font-medium">Total Processed</p>
              <p className="text-3xl font-bold text-fuchsia-700">
                {data?.total_processed.toLocaleString() || 0}
              </p>
            </div>
            <div className="bg-fuchsia-50 rounded-lg p-4">
              <p className="text-sm text-fuchsia-600 font-medium">Active Individuals</p>
              <p className="text-3xl font-bold text-fuchsia-700">
                {data?.unique_individuals || 0}
              </p>
            </div>
          </div>

          {/* Top Performers Chart */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-600 mb-3">
              Top 10 {view === 'speed' ? 'Fastest Processors' : 'Performers'} 
              {view === 'total' ? '(by Total Processed)' : view === 'daily' ? '(by Daily Average)' : '(by Processing Speed)'}
            </h3>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis type="number" tick={{ fontSize: 11 }} stroke="#9ca3af" />
                  <YAxis
                    dataKey="name"
                    type="category"
                    width={80}
                    tick={{ fontSize: 11 }}
                    stroke="#9ca3af"
                  />
                  <Tooltip
                    formatter={(value: number) => [
                      view === 'speed' 
                        ? `${Math.round(value)} min` 
                        : view === 'total'
                        ? `${value.toLocaleString()} faxes`
                        : `${value.toFixed(1)} avg/day`,
                      view === 'total' ? 'Faxes' : view === 'daily' ? 'Avg/Day' : 'Median Time',
                    ]}
                    labelFormatter={(_, payload) =>
                      payload?.[0]?.payload?.fullName || ''
                    }
                  />
                  <Bar dataKey="value" fill="#d946ef" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Individual Table */}
          <div className="flex flex-col flex-1">
            <h3 className="text-sm font-medium text-gray-600 mb-3">
              Faxes Processed by Individual
            </h3>
            <div className="overflow-x-auto flex-1 overflow-y-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-4 py-1.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Name
                    </th>
                    <th className="px-4 py-1.5 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Total
                    </th>
                    <th className="px-4 py-1.5 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Daily Avg
                    </th>
                    <th className="px-4 py-1.5 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Median Time
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {sortedData.map((item, index) => (
                    <tr
                      key={item.user_id}
                      className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                    >
                      <td className="px-4 py-1.5 whitespace-nowrap text-sm text-gray-900">
                        {item.user_name}
                      </td>
                      <td className="px-4 py-1.5 whitespace-nowrap text-sm text-gray-600 text-right">
                        {item.total_processed.toLocaleString()}
                      </td>
                      <td className="px-4 py-1.5 whitespace-nowrap text-sm text-gray-600 text-right">
                        {item.avg_per_day.toFixed(1)}
                      </td>
                      <td className="px-4 py-1.5 whitespace-nowrap text-sm text-gray-600 text-right">
                        {item.median_minutes ? `${Math.round(item.median_minutes)} min` : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      <Modal
        isOpen={showInfoModal}
        onClose={() => setShowInfoModal(false)}
        title="Productivity Calculations"
        colorClass="border-fuchsia-500"
      >
        <ProductivityCalculations />
      </Modal>
    </div>
  );
};
