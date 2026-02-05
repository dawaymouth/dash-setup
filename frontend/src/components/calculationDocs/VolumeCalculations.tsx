import React from 'react';

export const VolumeCalculations: React.FC = () => (
  <div className="space-y-4 text-sm">
    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Total Faxes Received</h4>
      <p className="text-gray-600">
        Count of all documents in the selected date range from the <code className="bg-gray-100 px-1 py-0.5 rounded text-xs">analytics.intake_documents</code> table.
      </p>
    </div>

    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Total Pages Received</h4>
      <p className="text-gray-600">
        Sum of page counts across all faxes. Data is joined from the <code className="bg-gray-100 px-1 py-0.5 rounded text-xs">workflow.documents</code> table using the document_id field.
      </p>
    </div>

    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Faxes Over Time</h4>
      <p className="text-gray-600 mb-2">
        Documents grouped by time period and counted:
      </p>
      <ul className="list-disc list-inside text-gray-600 space-y-1 ml-2">
        <li><span className="font-medium">Day:</span> Groups by calendar day</li>
        <li><span className="font-medium">Week:</span> Groups by ISO week (Monday start)</li>
        <li><span className="font-medium">Month:</span> Groups by calendar month</li>
      </ul>
    </div>

    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Time of Day Distribution</h4>
      <p className="text-gray-600">
        Faxes grouped by hour of receipt (0-23). The hour is determined by converting UTC timestamps to your browser's local timezone. This shows when faxes are typically received throughout a 24-hour period.
      </p>
    </div>

    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Category Distribution</h4>
      <p className="text-gray-600">
        Order categories grouped by product type from the <code className="bg-gray-100 px-1 py-0.5 rounded text-xs">analytics.order_skus</code> table. Shows the top 20 categories by order count with their percentage of total orders.
      </p>
    </div>

    <div className="bg-blue-50 border-l-4 border-blue-400 p-3 mt-4">
      <p className="text-xs text-blue-800">
        <span className="font-semibold">Note:</span> All metrics respect the selected date range and filter settings (AI Intake Only, Supplier, Organization).
      </p>
    </div>
  </div>
);
