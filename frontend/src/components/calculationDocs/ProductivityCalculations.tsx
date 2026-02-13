import React from 'react';

export const ProductivityCalculations: React.FC = () => (
  <div className="space-y-4 text-sm">
    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Total Processed</h4>
      <p className="text-gray-600 mb-2">
        Count of all documents that have been processed (any state except <code className="bg-gray-100 px-1 py-0.5 rounded text-xs">new</code>).
      </p>
      <p className="text-gray-600 text-xs mb-1">
        <span className="font-medium">Included states (7 total):</span>
      </p>
      <ul className="list-disc list-inside text-gray-600 text-xs space-y-0.5 ml-2">
        <li><code className="bg-gray-100 px-1 py-0.5 rounded text-xs">assigned</code> - Document assigned to an order (new or existing)</li>
        <li><code className="bg-gray-100 px-1 py-0.5 rounded text-xs">discarded</code> - Document marked as discarded</li>
        <li><code className="bg-gray-100 px-1 py-0.5 rounded text-xs">emailed</code> - Document sent via email</li>
        <li><code className="bg-gray-100 px-1 py-0.5 rounded text-xs">pushed</code> - Document pushed to destination</li>
        <li><code className="bg-gray-100 px-1 py-0.5 rounded text-xs">split</code> - Document split into multiple documents</li>
        <li><code className="bg-gray-100 px-1 py-0.5 rounded text-xs">splitting</code> - Document currently being split</li>
      </ul>
    </div>

    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Active Individuals</h4>
      <p className="text-gray-600">
        Unique count of users who accessed (touched) at least one document in the selected date range.
        Includes any user who has an access record for a document, not just the last person to complete it.
      </p>
    </div>

    <div>
      <h4 className="font-semibold text-gray-900 mb-1">By Individual (Total View)</h4>
      <p className="text-gray-600 mb-2">
        Documents attributed to the last user who accessed them, which typically represents who completed the terminal action. This provides better coverage than the assignee field.
      </p>
      <ul className="list-disc list-inside text-gray-600 space-y-1 ml-2">
        <li><span className="font-medium">Total:</span> Total documents processed by each user</li>
        <li><span className="font-medium">Daily Avg:</span> Total divided by calendar days in range</li>
        <li><span className="font-medium">Median Time:</span> Median processing time (explained below)</li>
      </ul>
    </div>

    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Daily Average View</h4>
      <p className="text-gray-600">
        Calculates average documents processed per active working day (not calendar days). Only includes days where the user processed at least one document.
      </p>
    </div>

    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Median Processing Time (Speed View)</h4>
      <p className="text-gray-600 mb-2">
        Time from first to last access by the same user, showing individual processing efficiency. Filters applied:
      </p>
      <ul className="list-disc list-inside text-gray-600 space-y-1 ml-2">
        <li>Only includes documents where first and last accessor are the same user</li>
        <li>Processing time must be greater than 0 minutes</li>
        <li>Processing time must be less than 1,440 minutes (24 hours)</li>
        <li>User must have at least 5 qualifying documents</li>
        <li>Uses median instead of average to reduce outlier impact</li>
      </ul>
    </div>

    <div className="bg-fuchsia-50 border-l-4 border-fuchsia-400 p-3 mt-4">
      <p className="text-xs text-fuchsia-800">
        <span className="font-semibold">Note:</span> Processing time is only calculated for documents where the same user did both the first and last access, representing a complete processing cycle.
      </p>
    </div>
  </div>
);
