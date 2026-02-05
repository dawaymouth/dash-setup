import axios from 'axios';
import { format } from 'date-fns';
import type {
  FaxVolumeResponse,
  CategoryDistributionResponse,
  PagesStatsResponse,
  TimeOfDayVolumeResponse,
  CycleTimeResponse,
  ProductivityResponse,
  CategoryByIndividualResponse,
  SupplierListResponse,
  SupplierOrganizationListResponse,
  PerFieldAccuracyResponse,
  DocumentAccuracyResponse,
  AccuracyTrendResponse,
  FilterState,
} from './types';
import { triggerVpnReminder } from './contexts/ErrorContext';

const api = axios.create({
  baseURL: '/api',
});

// Add response interceptor to catch API errors and show VPN reminder
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Trigger VPN reminder for any API error
    triggerVpnReminder();
    // Return rejected promise so React Query can handle the error normally
    return Promise.reject(error);
  }
);

// Helper to format dates for API
const formatDate = (date: Date) => format(date, 'yyyy-MM-dd');

// Helper to build query params
const buildParams = (filters: FilterState, extras: Record<string, string | number | boolean> = {}) => {
  const params: Record<string, string | number | boolean> = {
    start_date: formatDate(filters.startDate),
    end_date: formatDate(filters.endDate),
    ai_intake_only: filters.aiIntakeOnly,
    ...extras,
  };
  
  if (filters.supplierId) {
    params.supplier_id = filters.supplierId;
  }
  
  if (filters.supplierOrganizationId) {
    params.supplier_organization_id = filters.supplierOrganizationId;
  }
  
  return params;
};

// Volume endpoints
export const fetchFaxVolume = async (
  filters: FilterState,
  period: 'day' | 'week' | 'month' = 'day'
): Promise<FaxVolumeResponse> => {
  const { data} = await api.get('/volume/faxes', {
    params: buildParams(filters, { period }),
  });
  return data;
};

export const fetchFaxVolumeTrend = async (
  filterSubset: { aiIntakeOnly: boolean; supplierId: string | null; supplierOrganizationId: string | null },
  startDate: Date,
  endDate: Date,
  period: 'week' = 'week'
): Promise<FaxVolumeResponse> => {
  const params: Record<string, string | boolean> = {
    start_date: formatDate(startDate),
    end_date: formatDate(endDate),
    ai_intake_only: filterSubset.aiIntakeOnly,
    period,
  };
  
  if (filterSubset.supplierId) {
    params.supplier_id = filterSubset.supplierId;
  }
  
  if (filterSubset.supplierOrganizationId) {
    params.supplier_organization_id = filterSubset.supplierOrganizationId;
  }
  
  const { data } = await api.get('/volume/faxes', { params });
  return data;
};

export const fetchPagesStats = async (filters: FilterState): Promise<PagesStatsResponse> => {
  const { data } = await api.get('/volume/pages', {
    params: buildParams(filters),
  });
  return data;
};

export const fetchCategoryDistribution = async (
  filters: FilterState
): Promise<CategoryDistributionResponse> => {
  const { data } = await api.get('/volume/categories', {
    params: buildParams(filters),
  });
  return data;
};

export const fetchTimeOfDayVolume = async (
  filters: FilterState
): Promise<TimeOfDayVolumeResponse> => {
  const { data } = await api.get('/volume/time-of-day', {
    params: buildParams(filters),
  });
  return data;
};

// Cycle Time endpoints
export const fetchReceivedToOpenTime = async (
  filters: FilterState
): Promise<CycleTimeResponse> => {
  const { data } = await api.get('/cycle-time/received-to-open', {
    params: buildParams(filters),
  });
  return data;
};

export const fetchProcessingTime = async (filters: FilterState): Promise<CycleTimeResponse> => {
  const { data } = await api.get('/cycle-time/processing', {
    params: buildParams(filters),
  });
  return data;
};

// Productivity endpoints
export const fetchProductivityByIndividual = async (
  filters: FilterState,
  limit = 50
): Promise<ProductivityResponse> => {
  const { data } = await api.get('/productivity/by-individual', {
    params: buildParams(filters, { limit }),
  });
  return data;
};

export const fetchDailyAverageProductivity = async (
  filters: FilterState,
  limit = 50
): Promise<ProductivityResponse> => {
  const { data } = await api.get('/productivity/daily-average', {
    params: buildParams(filters, { limit }),
  });
  return data;
};

export const fetchCategoryByIndividual = async (
  filters: FilterState,
  limit = 20
): Promise<CategoryByIndividualResponse> => {
  const { data } = await api.get('/productivity/category-breakdown', {
    params: buildParams(filters, { limit }),
  });
  return data;
};

export const fetchProcessingTimeByIndividual = async (
  filters: FilterState,
  limit = 50
): Promise<ProductivityResponse> => {
  const { data } = await api.get('/productivity/by-individual-processing-time', {
    params: buildParams(filters, { limit }),
  });
  return data;
};

// Suppliers endpoints
export const fetchSuppliers = async (
  aiIntakeOnly = false,
  search?: string
): Promise<SupplierListResponse> => {
  const params: Record<string, string | boolean> = { ai_intake_only: aiIntakeOnly };
  if (search) params.search = search;
  
  const { data } = await api.get('/suppliers/', { params });
  return data;
};

export const fetchAiEnabledCount = async (): Promise<{ ai_enabled_count: number }> => {
  const { data } = await api.get('/suppliers/ai-enabled-count');
  return data;
};

export const fetchSupplierOrganizations = async (
  aiIntakeOnly = false,
  search?: string
): Promise<SupplierOrganizationListResponse> => {
  const params: Record<string, string | boolean> = { ai_intake_only: aiIntakeOnly };
  if (search) params.search = search;
  
  const { data } = await api.get('/suppliers/organizations', { params });
  return data;
};

// Accuracy endpoints
export const fetchPerFieldAccuracy = async (
  filters: FilterState
): Promise<PerFieldAccuracyResponse> => {
  const { data } = await api.get('/accuracy/per-field', {
    params: buildParams(filters),
  });
  return data;
};

export const fetchDocumentAccuracy = async (
  filters: FilterState
): Promise<DocumentAccuracyResponse> => {
  const { data } = await api.get('/accuracy/document-level', {
    params: buildParams(filters),
  });
  return data;
};

export const fetchAccuracyTrend = async (
  filters: FilterState,
  period: 'day' | 'week' = 'day'
): Promise<AccuracyTrendResponse> => {
  const { data } = await api.get('/accuracy/trend', {
    params: buildParams(filters, { period }),
  });
  return data;
};

export const fetchFieldAccuracyTrend = async (
  filterSubset: { aiIntakeOnly: boolean; supplierId: string | null; supplierOrganizationId: string | null },
  startDate: Date,
  endDate: Date,
  period: 'day' | 'week' = 'day'
): Promise<AccuracyTrendResponse> => {
  const params: Record<string, string | boolean> = {
    start_date: formatDate(startDate),
    end_date: formatDate(endDate),
    ai_intake_only: filterSubset.aiIntakeOnly,
    period,
  };
  
  if (filterSubset.supplierId) {
    params.supplier_id = filterSubset.supplierId;
  }
  
  if (filterSubset.supplierOrganizationId) {
    params.supplier_organization_id = filterSubset.supplierOrganizationId;
  }
  
  const { data } = await api.get('/accuracy/field-level-trend', { params });
  return data;
};
