import React, { useState, useMemo, useEffect, useRef } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { format, parseISO, subDays } from 'date-fns';
import type { FilterState, FieldAccuracy } from '../types';
import {
  usePerFieldAccuracy,
  useDocumentAccuracy,
  useFieldAccuracyTrend,
} from '../hooks/useMetrics';
import { fetchStaticMetadata } from '../api';
import { Modal } from './Modal';
import { InfoButton } from './InfoButton';
import { AccuracyCalculations } from './calculationDocs';

interface AccuracyMetricsProps {
  filters: FilterState;
}

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

// Calculate linear regression for trend line
const calculateLinearRegression = (data: Array<{date: string; accuracy_pct: number}>) => {
  if (!data || data.length < 2) return null;
  
  // Convert dates to numeric x-values (0, 1, 2, ...)
  const n = data.length;
  const xValues = Array.from({length: n}, (_, i) => i);
  const yValues = data.map(d => d.accuracy_pct);
  
  // Calculate means
  const xMean = xValues.reduce((a, b) => a + b, 0) / n;
  const yMean = yValues.reduce((a, b) => a + b, 0) / n;
  
  // Calculate slope (m) and intercept (b) for y = mx + b
  let numerator = 0;
  let denominator = 0;
  
  for (let i = 0; i < n; i++) {
    numerator += (xValues[i] - xMean) * (yValues[i] - yMean);
    denominator += Math.pow(xValues[i] - xMean, 2);
  }
  
  const slope = numerator / denominator;
  const intercept = yMean - slope * xMean;
  
  // Generate trend line data points
  return data.map((d, i) => ({
    date: d.date,
    trend: slope * i + intercept
  }));
};

const STATIC_MODE = import.meta.env.VITE_STATIC_DATA === 'true';

export const AccuracyMetrics: React.FC<AccuracyMetricsProps> = ({ filters }) => {
  const [showInfoModal, setShowInfoModal] = useState(false);
  const [trendTimeWindow, setTrendTimeWindow] = useState<30 | 60 | 90 | 180 | 365>(30);
  const [staticExportEndDate, setStaticExportEndDate] = useState<Date | null>(null);

  const { data: fieldAccuracyData, isLoading: fieldLoading } =
    usePerFieldAccuracy(filters);
  const { data: docAccuracyData, isLoading: docLoading } =
    useDocumentAccuracy(filters);

  useEffect(() => {
    if (STATIC_MODE) {
      fetchStaticMetadata().then((meta) => {
        const end = meta?.date_range?.end_date;
        if (end) setStaticExportEndDate(new Date(end + 'T00:00:00'));
      });
    }
  }, []);

  // In static mode use export end date so chart aligns with export; else use today (stable ref)
  const todayRef = useRef(new Date());
  const trendEndDate = useMemo(() => {
    if (STATIC_MODE && staticExportEndDate) return staticExportEndDate;
    return todayRef.current;
  }, [staticExportEndDate]);
  const trendStartDate = useMemo(
    () => subDays(trendEndDate, trendTimeWindow),
    [trendEndDate, trendTimeWindow]
  );

  const { data: fieldTrendData, isLoading: fieldTrendLoading } = useFieldAccuracyTrend(
    {
      aiIntakeOnly: filters.aiIntakeOnly,
      supplierId: filters.supplierId,
      supplierOrganizationId: filters.supplierOrganizationId,
    },
    trendStartDate,
    trendEndDate,
    'week'
  );

  // Merge actual data with linear regression trend line data
  const chartData = useMemo(() => {
    if (!fieldTrendData?.data) return [];
    
    const trendData = calculateLinearRegression(fieldTrendData.data);
    
    return fieldTrendData.data.map((point, index) => ({
      ...point,
      trend: trendData?.[index]?.trend ?? null
    }));
  }, [fieldTrendData?.data]);

  const isLoading = fieldLoading || docLoading;

  // Bucket fields by accuracy range
  const bucketedFields = ACCURACY_BUCKETS.map((bucket) => {
    const fields = (fieldAccuracyData?.data || [])
      .filter((f) => f.accuracy_pct >= bucket.min && f.accuracy_pct < bucket.max)
      .sort((a, b) => {
        // Sort all fields by accuracy: highest to lowest (best first)
        return b.accuracy_pct - a.accuracy_pct;
      });
    return { ...bucket, fields };
  });

  // Field item component with compact list display
  const FieldItem: React.FC<{ field: FieldAccuracy }> = ({ field }) => (
    <div className="flex items-center justify-between text-xs py-0.5 hover:bg-white hover:bg-opacity-30 px-1 rounded break-inside-avoid">
      <span className="truncate">
        <span className="font-medium">{formatRecordType(field.record_type ?? '')}</span>: {formatFieldName(field.field_identifier ?? '')}
      </span>
      <span className="ml-2 flex-shrink-0 font-mono">{(field.accuracy_pct ?? 0).toFixed(1)}%</span>
    </div>
  );

  return (
    <div className="bg-white rounded-lg shadow-sm border-l-4 border-l-blue-500 border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800 flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-blue-500"></div>
          Accuracy
          <InfoButton onClick={() => setShowInfoModal(true)} />
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
                Field Accuracy
              </p>
              <p className="text-3xl font-bold text-blue-700">
                {(fieldAccuracyData?.overall_accuracy_pct ?? 0).toFixed(1)}%
              </p>
              <p className="text-xs text-blue-500 mt-1">
                {fieldAccuracyData?.total_fields ?? 0} fields tracked
              </p>
            </div>
            <div className="bg-green-50 rounded-lg p-4">
              <p className="text-sm text-green-600 font-medium">
                No Edits Made
              </p>
              <p className="text-3xl font-bold text-green-700">
                {(docAccuracyData?.accuracy_pct ?? 0).toFixed(1)}%
              </p>
              <p className="text-xs text-green-500 mt-1">
                {(docAccuracyData?.docs_no_edits ?? 0).toLocaleString()} documents
              </p>
            </div>
            <div className="bg-orange-50 rounded-lg p-4">
              <p className="text-sm text-orange-600 font-medium">
                Edits Made
              </p>
              <p className="text-3xl font-bold text-orange-700">
                {(100 - (docAccuracyData?.accuracy_pct ?? 0)).toFixed(1)}%
              </p>
              <p className="text-xs text-orange-500 mt-1">
                {(docAccuracyData?.docs_with_edits ?? 0).toLocaleString()} documents
              </p>
            </div>
          </div>

          {/* Field Accuracy Trend */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-600 mb-3">
              Field Accuracy Trend
            </h3>
            
            {/* Controls stacked vertically */}
            <div className="space-y-2 mb-3">
              {/* Row 1: Time presets */}
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
                          ? 'bg-blue-500 text-white'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            
            <div className="bg-white border border-gray-200 rounded-lg p-4 h-64">
              {fieldTrendLoading ? (
                <div className="flex items-center justify-center h-full">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                </div>
              ) : !fieldTrendData?.data || fieldTrendData.data.length === 0 ? (
                <div className="flex items-center justify-center h-full text-gray-500 text-sm">
                  No trend data available for the selected period
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis
                      dataKey="date"
                      tickFormatter={(dateStr) => format(parseISO(dateStr), 'MMM d')}
                      tick={{ fontSize: 11 }}
                      stroke="#9ca3af"
                    />
                    <YAxis
                      domain={[90, 100]}
                      tick={{ fontSize: 11 }}
                      stroke="#9ca3af"
                      tickFormatter={(value) => `${value}%`}
                    />
                    <Tooltip
                      labelFormatter={(label) => format(parseISO(label as string), 'MMM d, yyyy')}
                      formatter={(value: number, name: string) => {
                        if (name === 'Trend') return [`${value.toFixed(1)}%`, 'Trend'];
                        return [`${value.toFixed(1)}%`, 'Field Accuracy'];
                      }}
                    />
                    {/* Main data line - no dots for cleaner look */}
                    <Line
                      type="monotone"
                      dataKey="accuracy_pct"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 5 }}
                      name="Field Accuracy"
                    />
                    {/* Linear regression trend line - dashed with different color */}
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
              )}
            </div>
          </div>

          {/* Per-Field Accuracy Quadrants */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-600 mb-3">
              Field Accuracy
            </h3>
            <div className="space-y-4">
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
                  <div className="max-h-64 overflow-y-auto">
                    {bucket.fields.length > 0 ? (
                      <div 
                        className="space-y-0.5"
                        style={{
                          columnCount: bucket.fields.length > 15 ? 2 : 1,
                          columnGap: '1rem'
                        }}
                      >
                        {bucket.fields.map((field) => (
                          <FieldItem
                            key={`${field.record_type}-${field.field_identifier}`}
                            field={field}
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
        </>
      )}

      <Modal
        isOpen={showInfoModal}
        onClose={() => setShowInfoModal(false)}
        title="Accuracy Calculations"
        colorClass="border-blue-500"
      >
        <AccuracyCalculations />
      </Modal>
    </div>
  );
};
