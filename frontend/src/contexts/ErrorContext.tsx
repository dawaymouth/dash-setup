import React, { createContext, useContext, useState, ReactNode, useEffect } from 'react';

interface ErrorContextType {
  showVpnReminder: () => void;
  hideVpnReminder: () => void;
  isVpnReminderVisible: boolean;
}

const ErrorContext = createContext<ErrorContextType | undefined>(undefined);

// Module-level reference to allow non-React code to trigger the VPN reminder
let globalShowVpnReminder: (() => void) | null = null;

export const triggerVpnReminder = () => {
  if (globalShowVpnReminder) {
    globalShowVpnReminder();
  }
};

export const useError = () => {
  const context = useContext(ErrorContext);
  if (!context) {
    throw new Error('useError must be used within an ErrorProvider');
  }
  return context;
};

interface ErrorProviderProps {
  children: ReactNode;
}

export const ErrorProvider: React.FC<ErrorProviderProps> = ({ children }) => {
  const [isVpnReminderVisible, setIsVpnReminderVisible] = useState(false);

  const showVpnReminder = () => {
    setIsVpnReminderVisible(true);
  };

  const hideVpnReminder = () => {
    setIsVpnReminderVisible(false);
  };

  // Register the showVpnReminder function globally so it can be called from axios interceptor
  useEffect(() => {
    globalShowVpnReminder = showVpnReminder;
    return () => {
      globalShowVpnReminder = null;
    };
  }, []);

  const value = {
    showVpnReminder,
    hideVpnReminder,
    isVpnReminderVisible,
  };

  return <ErrorContext.Provider value={value}>{children}</ErrorContext.Provider>;
};
