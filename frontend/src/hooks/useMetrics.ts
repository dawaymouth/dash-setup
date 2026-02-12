import { useQuery } from '@tanstack/react-query';
import type { FilterState } from '../types';
import {
  fetchFaxVolume,
  fetchFaxVolumeTrend,
  fetchPagesStats,
  fetchCategoryDistribution,
  fetchTimeOfDayVolume,
  fetchReceivedToOpenTime,
  fetchProcessingTime,
  fetchStateDistribution,
  fetchStateDistributionByUser,
  fetchProductivityByIndividual,
  fetchDailyAverageProductivity,
  fetchCategoryByIndividual,
  fetchCategoryByUser,
  fetchProcessingTimeByIndividual,
  fetchSuppliers,
  fetchSupplierOrganizations,
  fetchAiEnabledCount,
  fetchPerFieldAccuracy,
  fetchDocumentAccuracy,
  fetchAccuracyTrend,
  fetchFieldAccuracyTrend,
} from '../api';

// Volume hooks
export const useFaxVolume = (filters: FilterState, period: 'day' | 'week' | 'month' = 'day') => {
  return useQuery({
    queryKey: ['faxVolume', filters, period],
    queryFn: () => fetchFaxVolume(filters, period),
  });
};

export const useFaxVolumeTrend = (
  filters: { aiIntakeOnly: boolean; supplierId: string | null; supplierOrganizationId: string | null },
  startDate: Date,
  endDate: Date,
  period: 'week' = 'week'
) => {
  // Serialize dates in key so changing Range (30d/90d/etc.) triggers a new query
  const startStr = startDate.toISOString().slice(0, 10);
  const endStr = endDate.toISOString().slice(0, 10);
  return useQuery({
    queryKey: ['faxVolumeTrend', filters, startStr, endStr, period],
    queryFn: () => fetchFaxVolumeTrend(filters, startDate, endDate, period),
    retry: 2,
    staleTime: 5 * 60 * 1000,
  });
};

export const usePagesStats = (filters: FilterState) => {
  return useQuery({
    queryKey: ['pagesStats', filters],
    queryFn: () => fetchPagesStats(filters),
  });
};

export const useCategoryDistribution = (filters: FilterState) => {
  return useQuery({
    queryKey: ['categoryDistribution', filters],
    queryFn: () => fetchCategoryDistribution(filters),
  });
};

export const useTimeOfDayVolume = (filters: FilterState) => {
  return useQuery({
    queryKey: ['timeOfDayVolume', filters],
    queryFn: () => fetchTimeOfDayVolume(filters),
  });
};

// Cycle Time hooks
export const useReceivedToOpenTime = (filters: FilterState) => {
  return useQuery({
    queryKey: ['receivedToOpenTime', filters],
    queryFn: () => fetchReceivedToOpenTime(filters),
  });
};

export const useProcessingTime = (filters: FilterState) => {
  return useQuery({
    queryKey: ['processingTime', filters],
    queryFn: () => fetchProcessingTime(filters),
  });
};

export const useStateDistribution = (filters: FilterState) => {
  return useQuery({
    queryKey: ['stateDistribution', filters],
    queryFn: () => fetchStateDistribution(filters),
  });
};

// Productivity hooks
export const useProductivityByIndividual = (filters: FilterState, limit = 50) => {
  return useQuery({
    queryKey: ['productivityByIndividual', filters, limit],
    queryFn: () => fetchProductivityByIndividual(filters, limit),
  });
};

export const useDailyAverageProductivity = (filters: FilterState, limit = 50) => {
  return useQuery({
    queryKey: ['dailyAverageProductivity', filters, limit],
    queryFn: () => fetchDailyAverageProductivity(filters, limit),
  });
};

export const useCategoryByIndividual = (filters: FilterState, limit = 20) => {
  return useQuery({
    queryKey: ['categoryByIndividual', filters, limit],
    queryFn: () => fetchCategoryByIndividual(filters, limit),
  });
};

export const useCategoryByUser = (filters: FilterState, userId: string | null) => {
  return useQuery({
    queryKey: ['categoryByUser', filters, userId],
    queryFn: () => fetchCategoryByUser(filters, userId!),
    enabled: !!userId,
  });
};

export const useStateDistributionByUser = (filters: FilterState, userId: string | null) => {
  return useQuery({
    queryKey: ['stateDistributionByUser', filters, userId],
    queryFn: () => fetchStateDistributionByUser(filters, userId!),
    enabled: !!userId,
  });
};

export const useProcessingTimeByIndividual = (filters: FilterState, limit = 50) => {
  return useQuery({
    queryKey: ['processingTimeByIndividual', filters, limit],
    queryFn: () => fetchProcessingTimeByIndividual(filters, limit),
  });
};

// Supplier hooks
export const useSuppliers = (
  aiIntakeOnly = false,
  search?: string,
  supplierOrganizationId?: string | null
) => {
  return useQuery({
    queryKey: ['suppliers', aiIntakeOnly, search, supplierOrganizationId],
    queryFn: () => fetchSuppliers(aiIntakeOnly, search, supplierOrganizationId),
  });
};

export const useAiEnabledCount = () => {
  return useQuery({
    queryKey: ['aiEnabledCount'],
    queryFn: fetchAiEnabledCount,
  });
};

export const useSupplierOrganizations = (aiIntakeOnly = false, search?: string) => {
  return useQuery({
    queryKey: ['supplierOrganizations', aiIntakeOnly, search],
    queryFn: () => fetchSupplierOrganizations(aiIntakeOnly, search),
  });
};

// Accuracy hooks
export const usePerFieldAccuracy = (filters: FilterState) => {
  return useQuery({
    queryKey: ['perFieldAccuracy', filters],
    queryFn: () => fetchPerFieldAccuracy(filters),
  });
};

export const useDocumentAccuracy = (filters: FilterState) => {
  return useQuery({
    queryKey: ['documentAccuracy', filters],
    queryFn: () => fetchDocumentAccuracy(filters),
  });
};

export const useAccuracyTrend = (filters: FilterState, period: 'day' | 'week' = 'day') => {
  return useQuery({
    queryKey: ['accuracyTrend', filters, period],
    queryFn: () => fetchAccuracyTrend(filters, period),
  });
};

export const useFieldAccuracyTrend = (
  filters: { aiIntakeOnly: boolean; supplierId: string | null; supplierOrganizationId: string | null },
  startDate: Date,
  endDate: Date,
  period: 'day' | 'week' = 'day'
) => {
  // Serialize dates in key so changing Range (30d/90d/etc.) triggers a new query
  const startStr = startDate.toISOString().slice(0, 10);
  const endStr = endDate.toISOString().slice(0, 10);
  return useQuery({
    queryKey: ['fieldAccuracyTrend', filters, startStr, endStr, period],
    queryFn: () => fetchFieldAccuracyTrend(filters, startDate, endDate, period),
    retry: 2, // Only retry twice instead of default 3
    staleTime: 5 * 60 * 1000, // Consider data fresh for 5 minutes
  });
};
