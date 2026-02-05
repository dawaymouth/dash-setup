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
import { format, parseISO } from 'date-fns';
import type { FilterState, TimeOfDayDocument } from '../types';
import { useFaxVolume, usePagesStats, useCategoryDistribution, useTimeOfDayVolume } from '../hooks/useMetrics';

interface VolumeMetricsProps {
  filters: FilterState;
}

export const VolumeMetrics: React.FC<VolumeMetricsProps> = ({ filters }) => {
  const [period, setPeriod] = useState<'day' | 'week' | 'month' | 'time'>('day');
  
  const { data: volumeData, isLoading: volumeLoading } = useFaxVolume(filters, period === 'time' ? 'day' : period);
  const { data: timeData, isLoading: timeLoading } = useTimeOfDayVolume(filters);
  const { data: pagesData, isLoading: pagesLoading } = usePagesStats(filters);
  const { data: categoryData, isLoading: categoryLoading } = useCategoryDistribution(filters);

  const isLoading = (period === 'time' ? timeLoading : volumeLoading) || pagesLoading || categoryLoading;

  const formatXAxis = (dateStr: string) => {
    try {
      const date = parseISO(dateStr);
      if (period === 'month') return format(date, 'MMM yyyy');
      if (period === 'week') return format(date, 'MMM d');
      return format(date, 'MMM d');
    } catch {
      return dateStr;
    }
  };

  // Transform time-of-day data into bucketed chart data
  const timeChartData = useMemo(() => {
    if (!timeData?.data || period !== 'time') return [];

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
  }, [timeData, period]);

  // Determine which data and total to display
  const displayData = period === 'time' ? timeChartData : (volumeData?.data || []);
  const displayTotal = period === 'time' ? (timeData?.total || 0) : (volumeData?.total || 0);

  return (
    <div className="bg-white rounded-lg shadow-sm border-l-4 border-l-green-500 border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800 flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-green-500"></div>
          Volume
        </h2>
        <div className="flex gap-2">
          {(['day', 'week', 'month', 'time'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                period === p
                  ? 'bg-green-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {p.charAt(0).toUpperCase() + p.slice(1)}
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
                {displayTotal.toLocaleString()}
              </p>
            </div>
            <div className="bg-green-50 rounded-lg p-4">
              <p className="text-sm text-green-600 font-medium">Total Pages Received</p>
              <p className="text-3xl font-bold text-green-700">
                {pagesData?.total_pages.toLocaleString() || 0}
              </p>
            </div>
          </div>

          {/* Volume Chart */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-600 mb-3">
              {period === 'time' ? 'Faxes Received by Time of Day' : 'Faxes Received Over Time'}
            </h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                {period === 'time' ? (
                  <BarChart data={displayData}>
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
                ) : (
                  <LineChart data={displayData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis
                      dataKey="date"
                      tickFormatter={formatXAxis}
                      tick={{ fontSize: 12 }}
                      stroke="#9ca3af"
                    />
                    <YAxis tick={{ fontSize: 12 }} stroke="#9ca3af" />
                    <Tooltip
                      labelFormatter={(label) => formatXAxis(label as string)}
                      formatter={(value: number) => [value.toLocaleString(), 'Faxes']}
                    />
                    <Line
                      type="monotone"
                      dataKey="count"
                      stroke="#22c55e"
                      strokeWidth={2}
                      dot={{ fill: '#22c55e', r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                )}
              </ResponsiveContainer>
            </div>
          </div>

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
                  {categoryData?.data
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
    </div>
  );
};
