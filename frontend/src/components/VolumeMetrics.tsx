import React, { useState, useMemo } from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { format, parseISO, subDays } from 'date-fns';
import type { FilterState } from '../types';
import { useFaxVolumeTrend, usePagesStats, useCategoryDistribution, useTimeOfDayVolume } from '../hooks/useMetrics';
import { Modal } from './Modal';
import { InfoButton } from './InfoButton';
import { VolumeCalculations } from './calculationDocs';

interface VolumeMetricsProps {
  filters: FilterState;
}

// Calculate linear regression for trend line
const calculateLinearRegression = (data: Array<{date: string; count: number}>) => {
  if (!data || data.length < 2) return null;
  
  const n = data.length;
  const xValues = Array.from({length: n}, (_, i) => i);
  const yValues = data.map(d => d.count);
  
  const xMean = xValues.reduce((a, b) => a + b, 0) / n;
  const yMean = yValues.reduce((a, b) => a + b, 0) / n;
  
  let numerator = 0;
  let denominator = 0;
  
  for (let i = 0; i < n; i++) {
    numerator += (xValues[i] - xMean) * (yValues[i] - yMean);
    denominator += Math.pow(xValues[i] - xMean, 2);
  }
  
  const slope = numerator / denominator;
  const intercept = yMean - slope * xMean;
  
  return data.map((d, i) => ({
    date: d.date,
    trend: slope * i + intercept
  }));
};

export const VolumeMetrics: React.FC<VolumeMetricsProps> = ({ filters }) => {
  const [viewMode, setViewMode] = useState<'chart' | 'time'>('chart');
  const [trendTimeWindow, setTrendTimeWindow] = useState<30 | 60 | 90 | 180 | 365>(30);
  const [showInfoModal, setShowInfoModal] = useState(false);
  
  // Calculate trend date range (independent of main dashboard filters)
  const trendEndDate = useMemo(() => new Date(), []);
  const trendStartDate = useMemo(
    () => subDays(trendEndDate, trendTimeWindow),
    [trendEndDate, trendTimeWindow]
  );
  
  const { data: timeData, isLoading: timeLoading } = useTimeOfDayVolume(filters);
  const { data: pagesData, isLoading: pagesLoading } = usePagesStats(filters);
  const { data: categoryData, isLoading: categoryLoading } = useCategoryDistribution(filters);
  
  const { data: volumeTrendData, isLoading: volumeTrendLoading } = useFaxVolumeTrend(
    {
      aiIntakeOnly: filters.aiIntakeOnly,
      supplierId: filters.supplierId,
      supplierOrganizationId: filters.supplierOrganizationId,
    },
    trendStartDate,
    trendEndDate,
    'week'
  );

  const isLoading = (viewMode === 'time' ? timeLoading : volumeTrendLoading) || pagesLoading || categoryLoading;

  // Merge actual data with linear regression trend line data
  const chartData = useMemo(() => {
    if (!volumeTrendData?.data) return [];
    
    const trendData = calculateLinearRegression(volumeTrendData.data);
    
    return volumeTrendData.data.map((point, index) => ({
      ...point,
      trend: trendData?.[index]?.trend ?? null
    }));
  }, [volumeTrendData?.data]);

  // Transform time-of-day data into bucketed chart data
  const timeChartData = useMemo(() => {
    if (!timeData?.data) return [];

    // Initialize all 24 hour buckets
    const hourBuckets: Record<number, number> = {};
    for (let i = 0; i < 24; i++) {
      hourBuckets[i] = 0;
    }

    // Process each timestamp and convert to local timezone
    timeData.data.forEach((item) => {
      // Parse ISO timestamp (comes as UTC from backend)
      const date = new Date(item.timestamp);
      
      // getHours() returns hour in browser's local timezone (0-23)
      const localHour = date.getHours();
      
      // Increment the hour bucket
      hourBuckets[localHour] += 1;
    });

    // Helper to format hour in 12-hour format with AM/PM
    const formatHour = (hour: number): string => {
      if (hour === 0) return '12 AM';
      if (hour < 12) return `${hour} AM`;
      if (hour === 12) return '12 PM';
      return `${hour - 12} PM`;
    };

    // Return all 24 hours in order
    return Array.from({ length: 24 }, (_, hour) => ({
      time: formatHour(hour),
      count: hourBuckets[hour],
      hour: hour, // Keep raw hour for debugging
    }));
  }, [timeData]);

  return (
    <div className="bg-white rounded-lg shadow-sm border-l-4 border-l-green-500 border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800 flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-green-500"></div>
          Volume
          <InfoButton onClick={() => setShowInfoModal(true)} />
        </h2>
        <div className="flex gap-2">
          {(['chart', 'time'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                viewMode === mode
                  ? 'bg-green-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {mode === 'chart' ? 'Chart' : 'Time'}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-500"></div>
        </div>
      ) : (
        <>
          {/* Stats Cards */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="bg-green-50 rounded-lg p-4">
              <p className="text-sm text-green-600 font-medium">Total Faxes Received</p>
              <p className="text-3xl font-bold text-green-700">
                {(viewMode === 'time' ? timeData?.total : volumeTrendData?.total)?.toLocaleString() || 0}
              </p>
            </div>
            <div className="bg-green-50 rounded-lg p-4">
              <p className="text-sm text-green-600 font-medium">Total Pages Received</p>
              <p className="text-3xl font-bold text-green-700">
                {(pagesData?.total_pages ?? 0).toLocaleString()}
              </p>
            </div>
          </div>

          {/* Trend Chart with Range Controls */}
          {viewMode === 'chart' && (
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-600 mb-3">
                Faxes Received Over Time
              </h3>
              
              {/* Range buttons */}
              <div className="mb-3">
                <div className="flex gap-2 items-center">
                  <span className="text-xs text-gray-500 w-16">Range:</span>
                  <div className="flex gap-1">
                    {[
                      { days: 30, label: '30d' },
                      { days: 60, label: '60d' },
                      { days: 90, label: '90d' },
                      { days: 180, label: '6mo' },
                      { days: 365, label: '1yr' }
                    ].map(({ days, label }) => (
                      <button
                        key={days}
                        onClick={() => setTrendTimeWindow(days as 30 | 60 | 90 | 180 | 365)}
                        className={`px-2 py-1 text-xs rounded-md transition-colors ${
                          trendTimeWindow === days
                            ? 'bg-green-500 text-white'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis
                      dataKey="date"
                      tickFormatter={(dateStr) => format(parseISO(dateStr), 'MMM d')}
                      tick={{ fontSize: 12 }}
                      stroke="#9ca3af"
                    />
                    <YAxis tick={{ fontSize: 12 }} stroke="#9ca3af" />
                    <Tooltip
                      labelFormatter={(label) => format(parseISO(label as string), 'MMM d, yyyy')}
                      formatter={(value: number, name: string) => {
                        if (name === 'Trend') return [value.toLocaleString(), 'Trend'];
                        return [value.toLocaleString(), 'Faxes'];
                      }}
                    />
                    {/* Main data line - no dots */}
                    <Line
                      type="monotone"
                      dataKey="count"
                      stroke="#22c55e"
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 5 }}
                      name="Faxes"
                    />
                    {/* Trend line - dashed */}
                    <Line
                      type="monotone"
                      dataKey="trend"
                      stroke="#f59e0b"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      dot={false}
                      name="Trend"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Time of Day Chart */}
          {viewMode === 'time' && (
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-600 mb-3">
                Faxes Received by Time of Day
              </h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={timeChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis
                      dataKey="time"
                      tick={{ fontSize: 10 }}
                      stroke="#9ca3af"
                      angle={-45}
                      textAnchor="end"
                      height={80}
                    />
                    <YAxis tick={{ fontSize: 12 }} stroke="#9ca3af" />
                    <Tooltip
                      formatter={(value: number) => [value.toLocaleString(), 'Faxes']}
                    />
                    <Bar
                      dataKey="count"
                      fill="#22c55e"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Category Distribution */}
          <div className="flex flex-col flex-1">
            <h3 className="text-sm font-medium text-gray-600 mb-3">
              Category Distribution
            </h3>
            <div className="overflow-x-auto flex-1 overflow-y-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-4 py-1.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Category
                    </th>
                    <th className="px-4 py-1.5 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Percentage
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {(categoryData?.data ?? [])
                    .sort((a, b) => b.percentage - a.percentage)
                    .map((item, index) => (
                      <tr
                        key={index}
                        className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                      >
                        <td className="px-4 py-1.5 whitespace-nowrap text-sm text-gray-900">
                          {item.category}
                        </td>
                        <td className="px-4 py-1.5 whitespace-nowrap text-sm text-gray-600 text-right">
                          {item.percentage.toFixed(1)}%
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
        title="Volume Calculations"
        colorClass="border-green-500"
      >
        <VolumeCalculations />
      </Modal>
    </div>
  );
};
