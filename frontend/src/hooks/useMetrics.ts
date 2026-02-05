import { useQuery } from '@tanstack/react-query';
import type { FilterState } from '../types';
import {
  fetchFaxVolume,
  fetchPagesStats,
  fetchCategoryDistribution,
  fetchTimeOfDayVolume,
  fetchReceivedToOpenTime,
  fetchProcessingTime,
  fetchProductivityByIndividual,
  fetchDailyAverageProductivity,
  fetchCategoryByIndividual,
  fetchProcessingTimeByIndividual,
  fetchSuppliers,
  fetchSupplierOrganizations,
  fetchAiEnabledCount,
  fetchPerFieldAccuracy,
  fetchDocumentAccuracy,
  fetchAccuracyTrend,
} from '../api';

// Volume hooks
export const useFaxVolume = (filters: FilterState, period: 'day' | 'week' | 'month' = 'day') => {
  return useQuery({
    queryKey: ['faxVolume', filters, period],
    queryFn: () => fetchFaxVolume(filters, period),
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

export const useProcessingTimeByIndividual = (filters: FilterState, limit = 50) => {
  return useQuery({
    queryKey: ['processingTimeByIndividual', filters, limit],
    queryFn: () => fetchProcessingTimeByIndividual(filters, limit),
  });
};

// Supplier hooks
export const useSuppliers = (aiIntakeOnly = false, search?: string) => {
  return useQuery({
    queryKey: ['suppliers', aiIntakeOnly, search],
    queryFn: () => fetchSuppliers(aiIntakeOnly, search),
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
