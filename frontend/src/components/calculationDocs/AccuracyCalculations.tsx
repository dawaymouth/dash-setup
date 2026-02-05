import React from 'react';

export const AccuracyCalculations: React.FC = () => (
  <div className="space-y-4 text-sm">
    <div>
      <h4 className="font-semibold text-gray-900 mb-1">How Accuracy is Calculated</h4>
      <p className="text-gray-600 mb-2">
        Accuracy measures how often AI-extracted field values match the final values after user review. The comparison is case-insensitive.
      </p>
      <ul className="list-disc list-inside text-gray-600 space-y-1 ml-2">
        <li><span className="font-medium">Data source:</span> <code className="bg-gray-100 px-1 py-0.5 rounded text-xs">workflow.csr_inbox_state_data_audits</code></li>
        <li><span className="font-medium">Initial value:</span> First value where user_id IS NULL (system-set)</li>
        <li><span className="font-medium">Final value:</span> Last value in the audit trail</li>
        <li><span className="font-medium">Comparison:</span> Case-insensitive text match</li>
      </ul>
    </div>

    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Overall Field Accuracy</h4>
      <p className="text-gray-600">
        Percentage of individual field values that remained unchanged from initial AI extraction to final value. Only includes field types with at least 100 documents for statistical significance.
      </p>
    </div>

    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Per-Field Accuracy Categories</h4>
      <p className="text-gray-600 mb-2">
        Fields are grouped into accuracy ranges:
      </p>
      <ul className="list-disc list-inside text-gray-600 space-y-1 ml-2">
        <li><span className="font-medium text-green-700">Excellent:</span> 95-100% accuracy</li>
        <li><span className="font-medium text-blue-700">Good:</span> 90-95% accuracy</li>
        <li><span className="font-medium text-yellow-700">Needs Improvement:</span> 80-90% accuracy</li>
        <li><span className="font-medium text-red-700">Poor:</span> Below 80% accuracy</li>
      </ul>
    </div>

    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Document-Level Accuracy</h4>
      <p className="text-gray-600 mb-2">
        A document is considered accurate only if ALL of its system-preselected fields match the final values.
      </p>
      <ul className="list-disc list-inside text-gray-600 space-y-1 ml-2">
        <li><span className="font-medium">Documents Without Edits:</span> All fields remained unchanged</li>
        <li><span className="font-medium">Documents With Edits:</span> At least one field was modified</li>
        <li><span className="font-medium">Accuracy %:</span> (Documents without edits / Total documents) × 100</li>
      </ul>
    </div>

    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Accuracy Trend</h4>
      <p className="text-gray-600">
        Shows document-level accuracy over time (daily or weekly), helping identify improvements or issues in AI extraction quality.
      </p>
    </div>

    <div className="bg-blue-50 border-l-4 border-blue-400 p-3 mt-4">
      <p className="text-xs text-blue-800">
        <span className="font-semibold">Important:</span> Only fields initially populated by the AI system (not manually entered fields) are included in accuracy calculations. This ensures we're measuring AI performance, not user data entry.
      </p>
    </div>
  </div>
);
