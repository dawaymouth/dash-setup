import React from 'react';
import { useError } from '../contexts/ErrorContext';

export const VpnReminderBanner: React.FC = () => {
  const { isVpnReminderVisible, hideVpnReminder } = useError();

  if (!isVpnReminderVisible) {
    return null;
  }

  return (
    <div className="sticky top-0 z-50 animate-slide-down">
      <div className="bg-amber-50 border-b-2 border-amber-200 px-4 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <svg
              className="h-6 w-6 text-amber-600 flex-shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <div>
              <p className="text-sm font-medium text-amber-900">
                Are you connected to Zscaler?
              </p>
              <p className="text-xs text-amber-700 mt-0.5">
                Some features may not work without VPN access.
              </p>
            </div>
          </div>
          <button
            onClick={hideVpnReminder}
            className="flex-shrink-0 ml-4 inline-flex text-amber-600 hover:text-amber-800 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 focus:ring-offset-amber-50 rounded-md p-1.5 transition-colors"
            aria-label="Dismiss VPN reminder"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};
