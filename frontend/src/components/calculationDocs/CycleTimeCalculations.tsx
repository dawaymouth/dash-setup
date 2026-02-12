import React from 'react';

export const CycleTimeCalculations: React.FC = () => (
  <div className="space-y-4 text-sm">
    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Median Received to Open</h4>
      <p className="text-gray-600 mb-2">
        Median time from when a fax is received (<code className="bg-gray-100 px-1 py-0.5 rounded text-xs">document_created_at</code>) to when it's first opened by a user (<code className="bg-gray-100 px-1 py-0.5 rounded text-xs">document_first_accessed_at</code>).
      </p>
      <p className="text-gray-600 mb-2 font-medium">Business Hours Calculation:</p>
      <ul className="list-disc list-inside text-gray-600 space-y-1 ml-2">
        <li><span className="font-medium">Business Hours:</span> Monday-Friday, 8:00 AM - 6:00 PM (10 hours/day)</li>
        <li><span className="font-medium">Method:</span> Only business-hour minutes are counted; nights and weekends are fully excluded</li>
        <li><span className="font-medium">Received outside hours:</span> Start time clipped to the next business-hour boundary</li>
        <li><span className="font-medium">Opened outside hours:</span> End time clipped to the most recent business-hour boundary</li>
        <li><span className="font-medium">Calculation:</span> Uses median instead of average to reduce outlier impact</li>
        <li><span className="font-medium">Outlier filter:</span> Excludes times greater than ~2 business weeks (6,000 minutes)</li>
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
      <h4 className="font-semibold text-gray-900 mb-1">Document Outcomes</h4>
      <p className="text-gray-600 mb-2">
        Percentage breakdown of processed documents by their terminal state. Assigned documents are split into: attached to an existing DME order, generated a new DME order, or other.
      </p>
      <ul className="list-disc list-inside text-gray-600 space-y-1 ml-2">
        <li><span className="font-medium">Pushed:</span> Document pushed to destination system</li>
        <li><span className="font-medium">Attached to existing order:</span> Assigned document attached to an existing DME order</li>
        <li><span className="font-medium">Generated new order:</span> Assigned document that generated a new DME order</li>
        <li><span className="font-medium">Assigned (other):</span> Assigned documents that are neither attached to existing nor generated new</li>
        <li><span className="font-medium">Emailed:</span> Document sent via email</li>
        <li><span className="font-medium">Discarded:</span> Document marked as discarded</li>
        <li><span className="font-medium">Split:</span> Document split into multiple documents (includes documents currently being split)</li>
      </ul>
    </div>

    <div>
      <h4 className="font-semibold text-gray-900 mb-1">Chart Display</h4>
      <p className="text-gray-600">
        The time charts show daily medians over the selected date range, allowing you to track trends and identify patterns in processing speed. The outcomes chart shows the overall distribution of document terminal states.
      </p>
    </div>

    <div className="bg-red-50 border-l-4 border-red-400 p-3 mt-4">
      <p className="text-xs text-red-800">
        <span className="font-semibold">Why Median?</span> Both time metrics use median instead of average. This prevents a few very long wait or processing times from skewing the overall metric, providing a more representative view of typical performance.
      </p>
    </div>
  </div>
);
