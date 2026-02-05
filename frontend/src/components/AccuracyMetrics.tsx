import React, { useState } from 'react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import type { FilterState, FieldAccuracy } from '../types';
import {
  usePerFieldAccuracy,
  useDocumentAccuracy,
  useAccuracyTrend,
} from '../hooks/useMetrics';

interface AccuracyMetricsProps {
  filters: FilterState;
}

const PIE_COLORS = ['#22c55e', '#ef4444']; // Green for no edits, red for edits

// Accuracy bucket configuration
const ACCURACY_BUCKETS = [
  { label: 'Excellent', range: '95-100%', min: 95, max: 101, bgColor: 'bg-green-50', borderColor: 'border-green-200', textColor: 'text-green-700', pillBg: 'bg-green-100', pillText: 'text-green-800' },
  { label: 'Good', range: '90-95%', min: 90, max: 95, bgColor: 'bg-blue-50', borderColor: 'border-blue-200', textColor: 'text-blue-700', pillBg: 'bg-blue-100', pillText: 'text-blue-800' },
  { label: 'Needs Improvement', range: '80-90%', min: 80, max: 90, bgColor: 'bg-yellow-50', borderColor: 'border-yellow-200', textColor: 'text-yellow-700', pillBg: 'bg-yellow-100', pillText: 'text-yellow-800' },
  { label: 'Poor', range: '<80%', min: 0, max: 80, bgColor: 'bg-red-50', borderColor: 'border-red-200', textColor: 'text-red-700', pillBg: 'bg-red-100', pillText: 'text-red-800' },
];

// Helper to format field names for display
const formatFieldName = (fieldId: string): string => {
  // Extract the field name after the last hyphen
  const parts = fieldId.split('-');
  const fieldName = parts[parts.length - 1];
  // Convert snake_case to Title Case
  return fieldName
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

// Helper to format record types
const formatRecordType = (recordType: string): string => {
  // Extract just the type name from "CsrInboxState::Patient" format
  const match = recordType.match(/::(\w+)$/);
  return match ? match[1] : recordType;
};

export const AccuracyMetrics: React.FC<AccuracyMetricsProps> = ({ filters }) => {
  const [trendPeriod, setTrendPeriod] = useState<'day' | 'week'>('day');

  const { data: fieldAccuracyData, isLoading: fieldLoading } =
    usePerFieldAccuracy(filters);
  const { data: docAccuracyData, isLoading: docLoading } =
    useDocumentAccuracy(filters);
  const { data: trendData, isLoading: trendLoading } = useAccuracyTrend(
    filters,
    trendPeriod
  );

  const isLoading = fieldLoading || docLoading || trendLoading;

  // Bucket fields by accuracy range
  const bucketedFields = ACCURACY_BUCKETS.map((bucket) => {
    const fields = (fieldAccuracyData?.data || [])
      .filter((f) => f.accuracy_pct >= bucket.min && f.accuracy_pct < bucket.max)
      .sort((a, b) => {
        // Sort by accuracy: highest first for Excellent/Good, lowest first for Poor
        if (bucket.min >= 90) {
          return b.accuracy_pct - a.accuracy_pct;
        }
        return a.accuracy_pct - b.accuracy_pct;
      });
    return { ...bucket, fields };
  });

  // Prepare data for pie chart
  const pieChartData = docAccuracyData
    ? [
        { name: 'No Edits Required', value: docAccuracyData.docs_no_edits },
        { name: 'User Edits Made', value: docAccuracyData.docs_with_edits },
      ]
    : [];

  const formatXAxis = (dateStr: string) => {
    try {
      const date = parseISO(dateStr);
      if (trendPeriod === 'week') return format(date, 'MMM d');
      return format(date, 'MMM d');
    } catch {
      return dateStr;
    }
  };

  // Field pill component with inline accuracy percentage
  const FieldPill: React.FC<{ field: FieldAccuracy; bucket: typeof ACCURACY_BUCKETS[0] }> = ({
    field,
    bucket,
  }) => (
    <span
      className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium ${bucket.pillBg} ${bucket.pillText}`}
    >
      {formatRecordType(field.record_type)}: {formatFieldName(field.field_identifier)}
      <span className="ml-1 opacity-75">({field.accuracy_pct.toFixed(1)}%)</span>
    </span>
  );

  return (
    <div className="bg-white rounded-lg shadow-sm border-l-4 border-l-blue-500 border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800 flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-blue-500"></div>
          Accuracy
        </h2>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      ) : (
        <>
          {/* Stats Cards */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-blue-50 rounded-lg p-4">
              <p className="text-sm text-blue-600 font-medium">
                Overall Field Accuracy
              </p>
              <p className="text-3xl font-bold text-blue-700">
                {fieldAccuracyData?.overall_accuracy_pct.toFixed(1) || 0}%
              </p>
              <p className="text-xs text-blue-500 mt-1">
                {fieldAccuracyData?.total_fields || 0} field types tracked
              </p>
            </div>
            <div className="bg-green-50 rounded-lg p-4">
              <p className="text-sm text-green-600 font-medium">
                Documents Without Edits
              </p>
              <p className="text-3xl font-bold text-green-700">
                {docAccuracyData?.docs_no_edits.toLocaleString() || 0}
              </p>
              <p className="text-xs text-green-500 mt-1">
                {docAccuracyData?.accuracy_pct.toFixed(1) || 0}% of AI docs
              </p>
            </div>
            <div className="bg-orange-50 rounded-lg p-4">
              <p className="text-sm text-orange-600 font-medium">
                Documents With Edits
              </p>
              <p className="text-3xl font-bold text-orange-700">
                {docAccuracyData?.docs_with_edits.toLocaleString() || 0}
              </p>
              <p className="text-xs text-orange-500 mt-1">
                of {docAccuracyData?.total_ai_docs.toLocaleString() || 0} total
              </p>
            </div>
          </div>

          {/* Per-Field Accuracy Quadrants */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-600 mb-3">
              Per-Field Accuracy by Category
            </h3>
            <div className="grid grid-cols-2 gap-4">
              {bucketedFields.map((bucket) => (
                <div
                  key={bucket.label}
                  className={`${bucket.bgColor} ${bucket.borderColor} border rounded-lg p-4`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <h4 className={`font-medium ${bucket.textColor}`}>
                      {bucket.label}
                    </h4>
                    <span className={`text-sm ${bucket.textColor}`}>
                      {bucket.range} ({bucket.fields.length})
                    </span>
                  </div>
                  <div className="max-h-32 overflow-y-auto">
                    {bucket.fields.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {bucket.fields.map((field) => (
                          <FieldPill
                            key={`${field.record_type}-${field.field_identifier}`}
                            field={field}
                            bucket={bucket}
                          />
                        ))}
                      </div>
                    ) : (
                      <p className={`text-sm ${bucket.textColor} opacity-60 italic`}>
                        No fields in this range
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Document Accuracy Pie Chart and Trend Chart */}
          <div className="grid grid-cols-2 gap-6">
            {/* Pie Chart */}
            <div>
              <h3 className="text-sm font-medium text-gray-600 mb-3">
                Document-Level Accuracy
              </h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieChartData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                      label={({ percent }) =>
                        `${(percent * 100).toFixed(0)}%`
                      }
                    >
                      {pieChartData.map((_, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={PIE_COLORS[index % PIE_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number, name: string) => [
                        `${value.toLocaleString()} documents`,
                        name,
                      ]}
                    />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Trend Chart */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-gray-600">
                  Document-Level Accuracy Trend
                </h3>
                <div className="flex gap-2">
                  {(['day', 'week'] as const).map((p) => (
                    <button
                      key={p}
                      onClick={() => setTrendPeriod(p)}
                      className={`px-2 py-1 text-xs rounded-md transition-colors ${
                        trendPeriod === p
                          ? 'bg-blue-500 text-white'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      {p.charAt(0).toUpperCase() + p.slice(1)}
                    </button>
                  ))}
                </div>
              </div>
              <div className="h-64">
                {!trendData?.data || trendData.data.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-gray-500 text-sm">
                    No trend data available for the selected period
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trendData.data}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis
                        dataKey="date"
                        tickFormatter={formatXAxis}
                        tick={{ fontSize: 11 }}
                        stroke="#9ca3af"
                      />
                      <YAxis
                        domain={['auto', 'auto']}
                        tick={{ fontSize: 11 }}
                        stroke="#9ca3af"
                        tickFormatter={(value) => `${value}%`}
                      />
                      <Tooltip
                        labelFormatter={(label) => formatXAxis(label as string)}
                        formatter={(value: number) => [
                          `${value.toFixed(1)}%`,
                          'Document Accuracy',
                        ]}
                      />
                      <Line
                        type="monotone"
                        dataKey="accuracy_pct"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        dot={{ fill: '#3b82f6', r: 3 }}
                        activeDot={{ r: 5 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
