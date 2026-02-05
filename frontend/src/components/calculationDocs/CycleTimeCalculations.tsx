import React from 'react';

export const CycleTimeCalculations: React.FC = () => (
  <div className="space-y-4 text-sm">
    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Avg Received to Open</h4>
      <p className="text-gray-600 mb-2">
        Average time from when a fax is received (<code className="bg-gray-100 px-1 py-0.5 rounded text-xs">document_created_at</code>) to when it's first opened by a user (<code className="bg-gray-100 px-1 py-0.5 rounded text-xs">document_first_accessed_at</code>).
      </p>
      <p className="text-gray-600 mb-2 font-medium">Business Hours Adjustment:</p>
      <ul className="list-disc list-inside text-gray-600 space-y-1 ml-2">
        <li><span className="font-medium">Business Hours:</span> Monday-Friday, 8:00 AM - 6:00 PM</li>
        <li><span className="font-medium">Weekend faxes:</span> Time counted from next Monday at 8:00 AM</li>
        <li><span className="font-medium">Before 8 AM:</span> Time counted from 8:00 AM same day</li>
        <li><span className="font-medium">After 6 PM:</span> Time counted from 8:00 AM next business day</li>
        <li><span className="font-medium">Outlier filter:</span> Excludes times greater than 1 week</li>
      </ul>
    </div>

    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Median Processing Time</h4>
      <p className="text-gray-600 mb-2">
        Median time from when a document is first opened (<code className="bg-gray-100 px-1 py-0.5 rounded text-xs">document_first_accessed_at</code>) to when it's marked as processed (<code className="bg-gray-100 px-1 py-0.5 rounded text-xs">intake_updated_at</code>).
      </p>
      <ul className="list-disc list-inside text-gray-600 space-y-1 ml-2">
        <li><span className="font-medium">States included:</span> All except "new" (pushed, assigned, emailed, etc.)</li>
        <li><span className="font-medium">Calculation:</span> Uses median instead of average to reduce outlier impact</li>
        <li><span className="font-medium">Outlier filter:</span> Excludes times greater than 1,440 minutes (24 hours)</li>
        <li><span className="font-medium">Validity check:</span> Only includes positive processing times</li>
      </ul>
    </div>

    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Chart Display</h4>
      <p className="text-gray-600">
        Both charts show daily averages over the selected date range, allowing you to track trends and identify patterns in processing speed.
      </p>
    </div>

    <div className="bg-red-50 border-l-4 border-red-400 p-3 mt-4">
      <p className="text-xs text-red-800">
        <span className="font-semibold">Why Median?</span> Using median instead of average prevents a few very long processing times from skewing the overall metric, providing a more representative view of typical processing speed.
      </p>
    </div>
  </div>
);
