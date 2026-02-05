// API Response Types

export interface FaxVolumeByDate {
  date: string;
  count: number;
}

export interface FaxVolumeResponse {
  data: FaxVolumeByDate[];
  total: number;
  period: 'day' | 'week' | 'month' | 'time';
}

export interface TimeOfDayDocument {
  timestamp: string;  // ISO 8601 UTC timestamp
}

export interface TimeOfDayVolumeResponse {
  data: TimeOfDayDocument[];
  total: number;
}

export interface CategoryDistribution {
  category: string;
  count: number;
  percentage: number;
}

export interface CategoryDistributionResponse {
  data: CategoryDistribution[];
  total: number;
}

export interface PagesStatsResponse {
  total_documents: number;
  total_pages: number;
  avg_pages_per_fax: number | null;
}

export interface CycleTimeByDate {
  date: string;
  avg_minutes: number;
  count: number;
}

export interface CycleTimeResponse {
  data: CycleTimeByDate[];
  overall_avg_minutes: number;
  metric_type: 'received_to_open' | 'processing';
}

export interface IndividualProductivity {
  user_id: string;
  user_name: string;
  total_processed: number;
  avg_per_day: number;
  median_minutes?: number;
}

export interface ProductivityResponse {
  data: IndividualProductivity[];
  total_processed: number;
  unique_individuals: number;
}

export interface CategoryByIndividual {
  user_id: string;
  user_name: string;
  category: string;
  count: number;
  percentage: number;
}

export interface CategoryByIndividualResponse {
  data: CategoryByIndividual[];
}

export interface Supplier {
  supplier_id: string;
  name: string;
  ai_intake_enabled: boolean;
}

export interface SupplierListResponse {
  data: Supplier[];
  total: number;
}

export interface SupplierOrganization {
  organization_id: string;
  name: string;
  num_suppliers: number;
  has_ai_intake: boolean;
}

export interface SupplierOrganizationListResponse {
  data: SupplierOrganization[];
  total: number;
}

// Accuracy Types
export interface FieldAccuracy {
  record_type: string;
  field_identifier: string;
  total_docs: number;  // Total documents with system-preselected values
  accurate_docs: number;  // Documents where value didn't change
  accuracy_pct: number;
}

export interface PerFieldAccuracyResponse {
  data: FieldAccuracy[];
  overall_accuracy_pct: number;
  total_fields: number;
}

export interface DocumentAccuracyResponse {
  total_ai_docs: number;  // Total docs with system-preselected fields
  docs_with_edits: number;  // Docs where at least one field changed
  docs_no_edits: number;  // Docs where all fields match (accurate)
  accuracy_pct: number;
}

export interface AccuracyTrendPoint {
  date: string;
  accuracy_pct: number;
  total_docs: number;  // Total documents for this period
  docs_with_changes: number;  // Documents where values changed
}

export interface AccuracyTrendResponse {
  data: AccuracyTrendPoint[];
  overall_accuracy_pct: number;
  period: 'day' | 'week';
}

// Filter State
export interface FilterState {
  startDate: Date;
  endDate: Date;
  aiIntakeOnly: boolean;
  supplierId: string | null;
  supplierOrganizationId: string | null;
}
