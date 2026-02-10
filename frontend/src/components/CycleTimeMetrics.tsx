import React, { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import type { FilterState } from '../types';
import { useReceivedToOpenTime, useProcessingTime, useStateDistribution } from '../hooks/useMetrics';
import { Modal } from './Modal';
import { InfoButton } from './InfoButton';
import { CycleTimeCalculations } from './calculationDocs';

// Distinct colours for each document-outcome state (red palette)
const STATE_COLORS: Record<string, string> = {
  pushed: '#dc2626',     // red-600
  assigned: '#ef4444',   // red-500
  emailed: '#f87171',    // red-400
  discarded: '#9f1239',  // rose-800
  split: '#fb923c',      // orange-400
};

interface CycleTimeMetricsProps {
  filters: FilterState;
}

export const CycleTimeMetrics: React.FC<CycleTimeMetricsProps> = ({ filters }) => {
  const [showInfoModal, setShowInfoModal] = useState(false);
  const { data: receivedToOpenData, isLoading: receivedLoading } = useReceivedToOpenTime(filters);
  const { data: processingData, isLoading: processingLoading } = useProcessingTime(filters);
  const { data: stateData, isLoading: stateLoading } = useStateDistribution(filters);

  const isLoading = receivedLoading || processingLoading || stateLoading;

  const formatXAxis = (dateStr: string) => {
    try {
      return format(parseISO(dateStr), 'MMM d');
    } catch {
      return dateStr;
    }
  };

  const formatMinutes = (minutes: number) => {
    if (minutes < 60) return `${Math.round(minutes)} min`;
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    return `${hours}h ${mins}m`;
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border-l-4 border-l-red-500 border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800 flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500"></div>
          Fax Processing Time
          <InfoButton onClick={() => setShowInfoModal(true)} />
        </h2>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-500"></div>
        </div>
      ) : (
        <>
          {/* Stats Cards */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="bg-red-50 rounded-lg p-4">
              <p className="text-sm text-red-600 font-medium">Median Received to Open</p>
              <p className="text-3xl font-bold text-red-700">
                {formatMinutes(receivedToOpenData?.overall_avg_minutes || 0)}
              </p>
              <p className="text-xs text-red-500 mt-1">
                (excluding non-business hours)
              </p>
            </div>
            <div className="bg-red-50 rounded-lg p-4">
              <p className="text-sm text-red-600 font-medium">Median Processing Time</p>
              <p className="text-3xl font-bold text-red-700">
                {formatMinutes(processingData?.overall_avg_minutes || 0)}
              </p>
              <p className="text-xs text-red-500 mt-1">
                (first open to processed)
              </p>
            </div>
          </div>

          {/* Received to Open Chart */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-600 mb-3">
              Received to Open Time (Business Hours)
            </h3>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={receivedToOpenData?.data || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatXAxis}
                    tick={{ fontSize: 11 }}
                    stroke="#9ca3af"
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    stroke="#9ca3af"
                    tickFormatter={(v) => `${Math.round(v)}m`}
                  />
                  <Tooltip
                    labelFormatter={(label) => formatXAxis(label as string)}
                    formatter={(value: number) => [formatMinutes(value), 'Median Time']}
                  />
                  <Bar dataKey="avg_minutes" fill="#ef4444" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Processing Time Chart */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-600 mb-3">
              Processing Time (First Open to Processed)
            </h3>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={processingData?.data || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatXAxis}
                    tick={{ fontSize: 11 }}
                    stroke="#9ca3af"
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    stroke="#9ca3af"
                    tickFormatter={(v) => `${Math.round(v)}m`}
                  />
                  <Tooltip
                    labelFormatter={(label) => formatXAxis(label as string)}
                    formatter={(value: number) => [formatMinutes(value), 'Median Time']}
                  />
                  <Bar dataKey="avg_minutes" fill="#dc2626" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Document Outcomes Chart */}
          {stateData && stateData.data.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-600 mb-3">
                Document Outcomes
              </h3>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stateData.data} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 11 }}
                      stroke="#9ca3af"
                      tickFormatter={(v) => `${v}%`}
                      domain={[0, 'auto']}
                    />
                    <YAxis
                      dataKey="label"
                      type="category"
                      width={80}
                      tick={{ fontSize: 11 }}
                      stroke="#9ca3af"
                    />
                    <Tooltip
                      formatter={(value: number, _name: string, props: { payload?: { count: number } }) => [
                        `${value}% (${(props.payload?.count ?? 0).toLocaleString()} faxes)`,
                        'Percentage',
                      ]}
                    />
                    <Bar dataKey="percentage" radius={[0, 4, 4, 0]}>
                      {stateData.data.map((entry) => (
                        <Cell
                          key={entry.state}
                          fill={STATE_COLORS[entry.state] || '#ef4444'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="text-xs text-gray-400 mt-1 text-right">
                Total: {(stateData?.total ?? 0).toLocaleString()} documents
              </p>
            </div>
          )}
        </>
      )}

      <Modal
        isOpen={showInfoModal}
        onClose={() => setShowInfoModal(false)}
        title="Fax Processing Time Calculations"
        colorClass="border-red-500"
      >
        <CycleTimeCalculations />
      </Modal>
    </div>
  );
};
