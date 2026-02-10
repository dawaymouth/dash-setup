import axios from 'axios';
import { format, startOfWeek } from 'date-fns';
import type {
  FaxVolumeResponse,
  CategoryDistributionResponse,
  PagesStatsResponse,
  TimeOfDayVolumeResponse,
  CycleTimeResponse,
  StateDistributionResponse,
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
import { decompressSync } from 'fflate';

// Check if running in static data mode
const STATIC_MODE = import.meta.env.VITE_STATIC_DATA === 'true';

const api = axios.create({
  baseURL: '/api',
});

// Add response interceptor to catch API errors and show VPN reminder
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Trigger VPN reminder for any API error (only in non-static mode)
    if (!STATIC_MODE) {
      triggerVpnReminder();
    }
    // Return rejected promise so React Query can handle the error normally
    return Promise.reject(error);
  }
);

// Static data cache (full dashboard: by_org + current org; legacy: single org)
let staticData: {
  organization?: any;
  suppliers?: any;
  perSupplier?: Record<string, any>;
  metadata?: any;
  currentSupplierId?: string | null;
  fullPayload?: { by_org?: Record<string, { organization: any; suppliers: any; per_supplier: Record<string, any> }> };
  currentOrganizationId?: string | null;
} = {
  currentSupplierId: null,
  currentOrganizationId: null,
};

function applyStaticOrg(orgId: string) {
  const byOrg = staticData.fullPayload?.by_org;
  if (!byOrg?.[orgId]) return;
  const slice = byOrg[orgId];
  staticData.organization = slice.organization;
  staticData.suppliers = slice.suppliers;
  staticData.perSupplier = slice.per_supplier;
  staticData.currentOrganizationId = orgId;
}

async function fetchDashboardJson(): Promise<any> {
  const gzUrl = '/data/dashboard-data.json.gz';
  const jsonUrl = '/data/dashboard-data.json';
  const gzRes = await fetch(gzUrl);
  if (gzRes.ok) {
    const buf = await gzRes.arrayBuffer();
    const decompressed = decompressSync(new Uint8Array(buf));
    const str = new TextDecoder().decode(decompressed);
    return JSON.parse(str);
  }
  const jsonRes = await fetch(jsonUrl);
  if (!jsonRes.ok) throw new Error('Missing dashboard data (tried .gz and .json)');
  return jsonRes.json();
}

// Load static data files (gzipped or fallback JSON); support single-org or by_org multi-org
async function loadStaticData() {
  if (staticData.metadata && (staticData.organization || staticData.fullPayload)) return; // Already loaded

  try {
    const [dashboardData, metadata] = await Promise.all([
      fetchDashboardJson(),
      fetch('/data/metadata.json').then((r) => r.json()),
    ]);

    staticData.metadata = metadata;

    if (dashboardData.by_org) {
      staticData.fullPayload = dashboardData;
      const orgs = metadata?.organizations || [];
      const savedOrgId = typeof localStorage !== 'undefined' ? localStorage.getItem('staticDashboardOrgId') : null;
      const orgId = savedOrgId && dashboardData.by_org[savedOrgId] ? savedOrgId : (orgs[0]?.id ?? null);
      if (orgId) applyStaticOrg(orgId);
    } else {
      staticData.organization = dashboardData.organization;
      staticData.suppliers = dashboardData.suppliers;
      staticData.perSupplier = dashboardData.per_supplier;
    }
  } catch (error) {
    console.error('Failed to load static data:', error);
    throw error;
  }
}

export function setStaticOrganizationId(orgId: string | null) {
  if (!STATIC_MODE) return;
  if (orgId) {
    applyStaticOrg(orgId);
    try {
      localStorage.setItem('staticDashboardOrgId', orgId);
    } catch (_) {}
  } else {
    staticData.currentOrganizationId = null;
  }
}

export function getStaticOrganizationId(): string | null {
  return STATIC_MODE ? staticData.currentOrganizationId ?? null : null;
}

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

// Update current supplier filter in static mode
export const setStaticSupplierFilter = (supplierId: string | null) => {
  if (STATIC_MODE) {
    staticData.currentSupplierId = supplierId;
  }
};

// ── Filtering & Aggregation Helpers ──────────────────────────────────

// Filter data by supplier_id
function filterBySupplier<T extends { supplier_id?: string }>(data: T[], supplierId: string | null | undefined): T[] {
  if (!supplierId) return data; // Show all if no filter
  return data.filter((item: T) => item.supplier_id === supplierId);
}

// Aggregate volume data: sum counts by date
function aggregateVolumeByDate(data: Array<{date: string, count: number, supplier_id?: string}>): Array<{date: string, count: number}> {
  const byDate = new Map<string, number>();
  for (const row of data) {
    byDate.set(row.date, (byDate.get(row.date) || 0) + row.count);
  }
  return Array.from(byDate.entries())
    .map(([date, count]) => ({ date, count }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

// Aggregate cycle time data: weighted average by date
function aggregateCycleTimeByDate(data: Array<{date: string, avg_minutes: number, count: number, supplier_id?: string}>): Array<{date: string, avg_minutes: number, count: number}> {
  const byDate = new Map<string, {weightedSum: number, totalCount: number}>();
  for (const row of data) {
    const existing = byDate.get(row.date);
    if (existing) {
      existing.weightedSum += row.avg_minutes * row.count;
      existing.totalCount += row.count;
    } else {
      byDate.set(row.date, { weightedSum: row.avg_minutes * row.count, totalCount: row.count });
    }
  }
  return Array.from(byDate.entries())
    .map(([d, v]) => ({
      date: d,
      avg_minutes: v.totalCount > 0 ? Math.round((v.weightedSum / v.totalCount) * 100) / 100 : 0,
      count: v.totalCount
    }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

// Compute overall weighted average for cycle time
function computeOverallAvg(data: Array<{avg_minutes: number, count: number}>): number {
  const totalCount = data.reduce((sum, r) => sum + r.count, 0);
  if (totalCount === 0) return 0;
  const weightedSum = data.reduce((sum, r) => sum + r.avg_minutes * r.count, 0);
  return Math.round((weightedSum / totalCount) * 100) / 100;
}

// Aggregate productivity data: sum by user
function aggregateProductivityByUser(data: Array<{user_id: string, user_name: string, total_processed: number, avg_per_day: number, median_minutes?: number | null, supplier_id?: string}>): Array<{user_id: string, user_name: string, total_processed: number, avg_per_day: number, median_minutes?: number}> {
  const byUser = new Map<string, {user_name: string, total: number, avgPerDay: number, medianWeightedSum: number, medianCount: number}>();
  for (const row of data) {
    const existing = byUser.get(row.user_id);
    if (existing) {
      existing.total += row.total_processed;
      existing.avgPerDay += row.avg_per_day;
      if (row.median_minutes != null) {
        existing.medianWeightedSum += row.median_minutes * row.total_processed;
        existing.medianCount += row.total_processed;
      }
    } else {
      byUser.set(row.user_id, {
        user_name: row.user_name,
        total: row.total_processed,
        avgPerDay: row.avg_per_day,
        medianWeightedSum: row.median_minutes != null ? row.median_minutes * row.total_processed : 0,
        medianCount: row.median_minutes != null ? row.total_processed : 0
      });
    }
  }
  return Array.from(byUser.entries())
    .map(([userId, v]) => ({
      user_id: userId,
      user_name: v.user_name,
      total_processed: v.total,
      avg_per_day: Math.round(v.avgPerDay * 100) / 100,
      median_minutes: v.medianCount > 0 ? Math.round((v.medianWeightedSum / v.medianCount) * 10) / 10 : undefined
    }))
    .sort((a, b) => b.total_processed - a.total_processed);
}

// Aggregate category by individual: sum by user+category
function aggregateCategoryByUser(data: Array<{user_id: string, user_name: string, category: string, count: number, percentage: number, supplier_id?: string}>): Array<{user_id: string, user_name: string, category: string, count: number, percentage: number}> {
  const byUserCat = new Map<string, {user_id: string, user_name: string, category: string, count: number}>();
  const userTotals = new Map<string, number>();
  for (const row of data) {
    const key = `${row.user_id}|||${row.category}`;
    const existing = byUserCat.get(key);
    if (existing) {
      existing.count += row.count;
    } else {
      byUserCat.set(key, { user_id: row.user_id, user_name: row.user_name, category: row.category, count: row.count });
    }
    userTotals.set(row.user_id, (userTotals.get(row.user_id) || 0) + row.count);
  }
  return Array.from(byUserCat.values())
    .map(v => ({
      ...v,
      percentage: Math.round((v.count / (userTotals.get(v.user_id) || 1) * 100) * 100) / 100
    }))
    .sort((a, b) => a.user_name.localeCompare(b.user_name) || b.count - a.count);
}

// Aggregate accuracy fields: sum by record_type+field_identifier
function aggregateFieldAccuracy(data: Array<{record_type: string, field_identifier: string, total_docs: number, accurate_docs: number, accuracy_pct: number, supplier_id?: string}>): Array<{record_type: string, field_identifier: string, total_docs: number, accurate_docs: number, accuracy_pct: number}> {
  const byField = new Map<string, {record_type: string, field_identifier: string, total_docs: number, accurate_docs: number}>();
  for (const row of data) {
    const key = `${row.record_type}|||${row.field_identifier}`;
    const existing = byField.get(key);
    if (existing) {
      existing.total_docs += row.total_docs;
      existing.accurate_docs += row.accurate_docs;
    } else {
      byField.set(key, { record_type: row.record_type, field_identifier: row.field_identifier, total_docs: row.total_docs, accurate_docs: row.accurate_docs });
    }
  }
  return Array.from(byField.values())
    .map(v => ({
      ...v,
      accuracy_pct: v.total_docs > 0 ? Math.round((v.accurate_docs / v.total_docs * 100) * 100) / 100 : 0
    }))
    .sort((a, b) => a.accuracy_pct - b.accuracy_pct);
}

// Aggregate accuracy trend: sum by date
function aggregateAccuracyTrend(data: Array<{date: string, accuracy_pct: number, total_docs: number, docs_with_changes: number, supplier_id?: string}>): Array<{date: string, accuracy_pct: number, total_docs: number, docs_with_changes: number}> {
  const byDate = new Map<string, {totalDocs: number, docsWithChanges: number}>();
  for (const row of data) {
    const existing = byDate.get(row.date);
    if (existing) {
      existing.totalDocs += row.total_docs;
      existing.docsWithChanges += row.docs_with_changes;
    } else {
      byDate.set(row.date, { totalDocs: row.total_docs, docsWithChanges: row.docs_with_changes });
    }
  }
  return Array.from(byDate.entries())
    .map(([d, v]) => ({
      date: d,
      total_docs: v.totalDocs,
      docs_with_changes: v.docsWithChanges,
      accuracy_pct: v.totalDocs > 0 ? Math.round(((v.totalDocs - v.docsWithChanges) / v.totalDocs * 100) * 100) / 100 : 0
    }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

// Aggregate category distribution: sum counts by category
function aggregateCategoryDistribution(data: Array<{category: string, count: number, percentage: number, supplier_id?: string}>): Array<{category: string, count: number, percentage: number}> {
  const byCat = new Map<string, number>();
  for (const row of data) {
    byCat.set(row.category, (byCat.get(row.category) || 0) + row.count);
  }
  const total = Array.from(byCat.values()).reduce((sum, c) => sum + c, 0);
  return Array.from(byCat.entries())
    .map(([category, count]) => ({
      category,
      count,
      percentage: total > 0 ? Math.round((count / total * 100) * 100) / 100 : 0
    }));
}

// ── Volume Endpoints ─────────────────────────────────────────────────

export const fetchFaxVolume = async (
  filters: FilterState,
  period: 'day' | 'week' | 'month' = 'day'
): Promise<FaxVolumeResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    const volumeData = (staticData.organization?.volume_by_day || []) as Array<{date: string, count: number, supplier_id?: string}>;
    const filtered = filterBySupplier(volumeData, staticData.currentSupplierId);
    const aggregated = aggregateVolumeByDate(filtered);
    const total = aggregated.reduce((sum, row) => sum + row.count, 0);
    return { data: aggregated, total, period: 'day' as const };
  }
  
  const { data } = await api.get('/volume/faxes', {
    params: buildParams(filters, { period }),
  });
  // Aggregate per-supplier rows by date for the internal dashboard
  const aggregated = aggregateVolumeByDate(data.data);
  return { ...data, data: aggregated, total: aggregated.reduce((s: number, r: {count: number}) => s + r.count, 0) };
};

export const fetchFaxVolumeTrend = async (
  filterSubset: { aiIntakeOnly: boolean; supplierId: string | null; supplierOrganizationId: string | null },
  startDate: Date,
  endDate: Date,
  period: 'week' = 'week'
): Promise<FaxVolumeResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    const volumeData = (staticData.organization?.volume_by_day || []) as Array<{date: string, count: number, supplier_id?: string}>;
    const filtered = filterBySupplier(volumeData, staticData.currentSupplierId);
    const aggregated = aggregateVolumeByDate(filtered);

    const startStr = formatDate(startDate);
    const endStr = formatDate(endDate);
    const inRange = aggregated.filter((row) => row.date >= startStr && row.date <= endStr);

    // Aggregate daily data into weekly buckets
    const weeklyMap = new Map<string, number>();
    for (const row of inRange) {
      const weekStart = startOfWeek(new Date(row.date + 'T00:00:00'), { weekStartsOn: 1 });
      const weekKey = format(weekStart, 'yyyy-MM-dd');
      weeklyMap.set(weekKey, (weeklyMap.get(weekKey) || 0) + row.count);
    }
    const weeklyData = Array.from(weeklyMap.entries())
      .map(([date, count]) => ({ date, count }))
      .sort((a, b) => a.date.localeCompare(b.date));

    const total = weeklyData.reduce((sum, row) => sum + row.count, 0);
    return { data: weeklyData, total, period: 'week' };
  }
  
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
  const aggregated = aggregateVolumeByDate(data.data);
  return { ...data, data: aggregated, total: aggregated.reduce((s: number, r: {count: number}) => s + r.count, 0) };
};

export const fetchPagesStats = async (filters: FilterState): Promise<PagesStatsResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    // Pages is a single aggregate — check per-supplier data first; always return an object
    const supplierId = staticData.currentSupplierId;
    const orgPages = staticData.organization?.pages;
    if (supplierId && staticData.perSupplier?.[supplierId]?.pages) {
      const p = staticData.perSupplier[supplierId].pages;
      return { total_documents: p?.total_documents ?? 0, total_pages: p?.total_pages ?? 0 };
    }
    return { total_documents: orgPages?.total_documents ?? 0, total_pages: orgPages?.total_pages ?? 0 };
  }
  
  const { data } = await api.get('/volume/pages', {
    params: buildParams(filters),
  });
  return data;
};

export const fetchCategoryDistribution = async (
  filters: FilterState
): Promise<CategoryDistributionResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    const categories = (staticData.organization?.categories || []) as Array<{category: string, count: number, percentage: number, supplier_id?: string}>;
    const filtered = filterBySupplier(categories, staticData.currentSupplierId);
    const aggregated = aggregateCategoryDistribution(filtered);
    const total = aggregated.reduce((sum, row) => sum + row.count, 0);
    return { data: aggregated, total };
  }
  
  const { data } = await api.get('/volume/categories', {
    params: buildParams(filters),
  });
  // Aggregate per-supplier rows by category
  const aggregated = aggregateCategoryDistribution(data.data);
  const total = aggregated.reduce((s: number, r: {count: number}) => s + r.count, 0);
  return { data: aggregated, total };
};

export const fetchTimeOfDayVolume = async (
  filters: FilterState
): Promise<TimeOfDayVolumeResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    const allData = (staticData.organization?.time_of_day?.data || []) as Array<{timestamp: string, supplier_id?: string}>;
    const filtered = filterBySupplier(allData, staticData.currentSupplierId);
    return { data: filtered, total: filtered.length };
  }
  
  const { data } = await api.get('/volume/time-of-day', {
    params: buildParams(filters),
  });
  return data;
};

// ── Cycle Time Endpoints ─────────────────────────────────────────────

export const fetchReceivedToOpenTime = async (
  filters: FilterState
): Promise<CycleTimeResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    const rawData = (staticData.organization?.cycle_time?.received_to_open?.data || []) as Array<{date: string, avg_minutes: number, count: number, supplier_id?: string}>;
    const filtered = filterBySupplier(rawData, staticData.currentSupplierId);
    const aggregated = aggregateCycleTimeByDate(filtered);
    return {
      data: aggregated,
      overall_avg_minutes: staticData.organization?.cycle_time?.received_to_open?.overall_avg_minutes ?? computeOverallAvg(aggregated),
      metric_type: 'received_to_open'
    };
  }
  
  const { data } = await api.get('/cycle-time/received-to-open', {
    params: buildParams(filters),
  });
  // Aggregate per-supplier rows by date for chart display
  const aggregated = aggregateCycleTimeByDate(data.data);
  return {
    data: aggregated,
    overall_avg_minutes: data.overall_avg_minutes,  // Use backend's true median
    metric_type: data.metric_type
  };
};

export const fetchProcessingTime = async (filters: FilterState): Promise<CycleTimeResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    const rawData = (staticData.organization?.cycle_time?.processing?.data || []) as Array<{date: string, avg_minutes: number, count: number, supplier_id?: string}>;
    const filtered = filterBySupplier(rawData, staticData.currentSupplierId);
    const aggregated = aggregateCycleTimeByDate(filtered);
    return {
      data: aggregated,
      overall_avg_minutes: staticData.organization?.cycle_time?.processing?.overall_avg_minutes ?? computeOverallAvg(aggregated),
      metric_type: 'processing'
    };
  }
  
  const { data } = await api.get('/cycle-time/processing', {
    params: buildParams(filters),
  });
  // Aggregate per-supplier rows by date for chart display
  const aggregated = aggregateCycleTimeByDate(data.data);
  return {
    data: aggregated,
    overall_avg_minutes: data.overall_avg_minutes,  // Use backend's true median
    metric_type: data.metric_type
  };
};

export const fetchStateDistribution = async (
  filters: FilterState
): Promise<StateDistributionResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    const staticResponse = staticData.organization?.cycle_time?.state_distribution;
    if (staticResponse && Array.isArray(staticResponse.data)) {
      return { data: staticResponse.data, total: staticResponse.total ?? 0 };
    }
    return { data: [], total: 0 };
  }

  const { data } = await api.get('/cycle-time/state-distribution', {
    params: buildParams(filters),
  });
  return data;
};

// ── Productivity Endpoints ───────────────────────────────────────────

export const fetchProductivityByIndividual = async (
  filters: FilterState,
  limit = 50
): Promise<ProductivityResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    const rawData = (staticData.organization?.productivity?.by_individual?.data || []) as Array<{user_id: string, user_name: string, total_processed: number, avg_per_day: number, median_minutes?: number | null, supplier_id?: string}>;
    const filtered = filterBySupplier(rawData, staticData.currentSupplierId);
    const aggregated = aggregateProductivityByUser(filtered);
    return {
      data: aggregated,
      total_processed: aggregated.reduce((s, r) => s + r.total_processed, 0),
      unique_individuals: aggregated.length
    };
  }
  
  const { data } = await api.get('/productivity/by-individual', {
    params: buildParams(filters, { limit }),
  });
  const aggregated = aggregateProductivityByUser(data.data);
  return {
    data: aggregated,
    total_processed: aggregated.reduce((s: number, r: {total_processed: number}) => s + r.total_processed, 0),
    unique_individuals: aggregated.length
  };
};

export const fetchDailyAverageProductivity = async (
  filters: FilterState,
  limit = 50
): Promise<ProductivityResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    const rawData = (staticData.organization?.productivity?.daily_average?.data || []) as Array<{user_id: string, user_name: string, total_processed: number, avg_per_day: number, median_minutes?: number | null, supplier_id?: string}>;
    const filtered = filterBySupplier(rawData, staticData.currentSupplierId);
    const aggregated = aggregateProductivityByUser(filtered);
    return {
      data: aggregated,
      total_processed: aggregated.reduce((s, r) => s + r.total_processed, 0),
      unique_individuals: aggregated.length
    };
  }
  
  const { data } = await api.get('/productivity/daily-average', {
    params: buildParams(filters, { limit }),
  });
  const aggregated = aggregateProductivityByUser(data.data);
  return {
    data: aggregated,
    total_processed: aggregated.reduce((s: number, r: {total_processed: number}) => s + r.total_processed, 0),
    unique_individuals: aggregated.length
  };
};

export const fetchCategoryByIndividual = async (
  filters: FilterState,
  limit = 20
): Promise<CategoryByIndividualResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    const rawData = (staticData.organization?.productivity?.category_breakdown?.data || []) as Array<{user_id: string, user_name: string, category: string, count: number, percentage: number, supplier_id?: string}>;
    const filtered = filterBySupplier(rawData, staticData.currentSupplierId);
    const aggregated = aggregateCategoryByUser(filtered);
    return { data: aggregated };
  }
  
  const { data } = await api.get('/productivity/category-breakdown', {
    params: buildParams(filters, { limit }),
  });
  const aggregated = aggregateCategoryByUser(data.data);
  return { data: aggregated };
};

export const fetchProcessingTimeByIndividual = async (
  filters: FilterState,
  limit = 50
): Promise<ProductivityResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    const rawData = (staticData.organization?.productivity?.by_individual_processing_time?.data
                 || staticData.organization?.productivity?.by_individual?.data || []) as Array<{user_id: string, user_name: string, total_processed: number, avg_per_day: number, median_minutes?: number | null, supplier_id?: string}>;
    const filtered = filterBySupplier(rawData, staticData.currentSupplierId);
    const aggregated = aggregateProductivityByUser(filtered);
    return {
      data: aggregated,
      total_processed: aggregated.reduce((s, r) => s + r.total_processed, 0),
      unique_individuals: aggregated.length
    };
  }
  
  const { data } = await api.get('/productivity/by-individual-processing-time', {
    params: buildParams(filters, { limit }),
  });
  const aggregated = aggregateProductivityByUser(data.data);
  return {
    data: aggregated,
    total_processed: aggregated.reduce((s: number, r: {total_processed: number}) => s + r.total_processed, 0),
    unique_individuals: aggregated.length
  };
};

// ── Supplier Endpoints ───────────────────────────────────────────────

export const fetchSuppliers = async (
  aiIntakeOnly = false,
  search?: string,
  supplierOrganizationId?: string | null
): Promise<SupplierListResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    // In static mode, return current org's suppliers (full dashboard) or legacy metadata.suppliers
    const suppliers = staticData.suppliers ?? staticData.metadata?.suppliers ?? [];
    return {
      data: suppliers,
      total: suppliers.length
    };
  }
  
  const params: Record<string, string | boolean> = { ai_intake_only: aiIntakeOnly };
  if (search) params.search = search;
  if (supplierOrganizationId) params.supplier_organization_id = supplierOrganizationId;
  
  const { data } = await api.get('/suppliers/', { params });
  return data;
};

export const fetchAiEnabledCount = async (): Promise<{ ai_enabled_count: number }> => {
  if (STATIC_MODE) {
    return { ai_enabled_count: 1 };
  }
  
  const { data } = await api.get('/suppliers/ai-enabled-count');
  return data;
};

export const fetchSupplierOrganizations = async (
  aiIntakeOnly = false,
  search?: string
): Promise<SupplierOrganizationListResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    // Full dashboard: metadata.organizations; legacy: metadata.supplier_organization
    const orgList = staticData.metadata?.organizations;
    if (Array.isArray(orgList) && orgList.length > 0) {
      return {
        data: orgList.map((o: { id: string; name: string; num_suppliers: number }) => ({
          organization_id: o.id,
          name: o.name,
          num_suppliers: o.num_suppliers ?? 0,
          has_ai_intake: true
        })),
        total: orgList.length
      };
    }
    const org = staticData.metadata?.supplier_organization;
    return {
      data: org ? [{
        organization_id: org.id,
        name: org.name,
        num_suppliers: org.num_suppliers || 0,
        has_ai_intake: true
      }] : [],
      total: org ? 1 : 0
    };
  }
  
  const params: Record<string, string | boolean> = { ai_intake_only: aiIntakeOnly };
  if (search) params.search = search;
  
  const { data } = await api.get('/suppliers/organizations', { params });
  return data;
};

// ── Accuracy Endpoints ───────────────────────────────────────────────

export const fetchPerFieldAccuracy = async (
  filters: FilterState
): Promise<PerFieldAccuracyResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    const rawData = (staticData.organization?.accuracy?.per_field?.data || []) as Array<{record_type: string, field_identifier: string, total_docs: number, accurate_docs: number, accuracy_pct: number, supplier_id?: string}>;
    const filtered = filterBySupplier(rawData, staticData.currentSupplierId);
    const aggregated = aggregateFieldAccuracy(filtered);
    const totalDocs = aggregated.reduce((s, r) => s + r.total_docs, 0);
    const totalAccurate = aggregated.reduce((s, r) => s + r.accurate_docs, 0);
    return {
      data: aggregated,
      overall_accuracy_pct: totalDocs > 0 ? Math.round((totalAccurate / totalDocs * 100) * 100) / 100 : 0,
      total_fields: aggregated.length
    };
  }
  
  const { data } = await api.get('/accuracy/per-field', {
    params: buildParams(filters),
  });
  // Aggregate per-supplier rows by field
  const aggregated = aggregateFieldAccuracy(data.data);
  const totalDocs = aggregated.reduce((s: number, r: {total_docs: number}) => s + r.total_docs, 0);
  const totalAccurate = aggregated.reduce((s: number, r: {accurate_docs: number}) => s + r.accurate_docs, 0);
  return {
    data: aggregated,
    overall_accuracy_pct: totalDocs > 0 ? Math.round((totalAccurate / totalDocs * 100) * 100) / 100 : 0,
    total_fields: aggregated.length
  };
};

export const fetchDocumentAccuracy = async (
  filters: FilterState
): Promise<DocumentAccuracyResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    // Document-level accuracy is a single aggregate — check per-supplier data first; always return a safe object
    const supplierId = staticData.currentSupplierId;
    const orgDoc = staticData.organization?.accuracy?.document_level;
    if (supplierId && staticData.perSupplier?.[supplierId]?.document_accuracy) {
      const d = staticData.perSupplier[supplierId].document_accuracy;
      return {
        total_ai_docs: d?.total_ai_docs ?? 0,
        docs_with_edits: d?.docs_with_edits ?? 0,
        docs_no_edits: d?.docs_no_edits ?? 0,
        accuracy_pct: d?.accuracy_pct ?? 0,
      };
    }
    return {
      total_ai_docs: orgDoc?.total_ai_docs ?? 0,
      docs_with_edits: orgDoc?.docs_with_edits ?? 0,
      docs_no_edits: orgDoc?.docs_no_edits ?? 0,
      accuracy_pct: orgDoc?.accuracy_pct ?? 0,
    };
  }
  
  const { data } = await api.get('/accuracy/document-level', {
    params: buildParams(filters),
  });
  return data;
};

export const fetchAccuracyTrend = async (
  filters: FilterState,
  period: 'day' | 'week' = 'day'
): Promise<AccuracyTrendResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    const rawData = (staticData.organization?.accuracy?.trend?.data || []) as Array<{date: string, accuracy_pct: number, total_docs: number, docs_with_changes: number, supplier_id?: string}>;
    const filtered = filterBySupplier(rawData, staticData.currentSupplierId);
    const aggregated = aggregateAccuracyTrend(filtered);
    const totalDocs = aggregated.reduce((s, r) => s + r.total_docs, 0);
    const totalChanges = aggregated.reduce((s, r) => s + r.docs_with_changes, 0);
    return {
      data: aggregated,
      overall_accuracy_pct: totalDocs > 0 ? Math.round(((totalDocs - totalChanges) / totalDocs * 100) * 100) / 100 : 0,
      period
    };
  }
  
  const { data } = await api.get('/accuracy/trend', {
    params: buildParams(filters, { period }),
  });
  const aggregated = aggregateAccuracyTrend(data.data);
  const totalDocs = aggregated.reduce((s: number, r: {total_docs: number}) => s + r.total_docs, 0);
  const totalChanges = aggregated.reduce((s: number, r: {docs_with_changes: number}) => s + r.docs_with_changes, 0);
  return {
    data: aggregated,
    overall_accuracy_pct: totalDocs > 0 ? Math.round(((totalDocs - totalChanges) / totalDocs * 100) * 100) / 100 : 0,
    period: data.period
  };
};

export const fetchFieldAccuracyTrend = async (
  filterSubset: { aiIntakeOnly: boolean; supplierId: string | null; supplierOrganizationId: string | null },
  startDate: Date,
  endDate: Date,
  period: 'day' | 'week' = 'day'
): Promise<AccuracyTrendResponse> => {
  if (STATIC_MODE) {
    await loadStaticData();
    // Field-level trend is stored under accuracy.field_level_trend or accuracy.trend
    const rawData = (staticData.organization?.accuracy?.field_level_trend?.data
                 || staticData.organization?.accuracy?.trend?.data || []) as Array<{date: string, accuracy_pct: number, total_docs: number, docs_with_changes: number, supplier_id?: string}>;
    const filtered = filterBySupplier(rawData, staticData.currentSupplierId);
    const startStr = formatDate(startDate);
    const endStr = formatDate(endDate);
    const inRange = filtered.filter((row) => row.date >= startStr && row.date <= endStr);
    const aggregated = aggregateAccuracyTrend(inRange);
    const totalDocs = aggregated.reduce((s, r) => s + r.total_docs, 0);
    const totalChanges = aggregated.reduce((s, r) => s + r.docs_with_changes, 0);
    return {
      data: aggregated,
      overall_accuracy_pct: totalDocs > 0 ? Math.round(((totalDocs - totalChanges) / totalDocs * 100) * 100) / 100 : 0,
      period
    };
  }
  
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
  const aggregated = aggregateAccuracyTrend(data.data);
  const totalDocs = aggregated.reduce((s: number, r: {total_docs: number}) => s + r.total_docs, 0);
  const totalChanges = aggregated.reduce((s: number, r: {docs_with_changes: number}) => s + r.docs_with_changes, 0);
  return {
    data: aggregated,
    overall_accuracy_pct: totalDocs > 0 ? Math.round(((totalDocs - totalChanges) / totalDocs * 100) * 100) / 100 : 0,
    period: data.period
  };
};

// Export metadata for static mode
export const fetchStaticMetadata = async () => {
  if (STATIC_MODE) {
    await loadStaticData();
    return staticData.metadata;
  }
  return null;
};
