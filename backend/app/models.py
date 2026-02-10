"""
Pydantic models for API request/response schemas.
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


# Request Models
class DateRangeParams(BaseModel):
    """Common date range parameters for filtering."""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    ai_intake_only: bool = False
    supplier_id: Optional[str] = None


# Response Models - Volume Metrics
class FaxVolumeByDate(BaseModel):
    """Fax volume for a specific date."""
    date: date
    count: int
    supplier_id: Optional[str] = None  # For client-side filtering by supplier


class FaxVolumeResponse(BaseModel):
    """Response for fax volume endpoint."""
    data: list[FaxVolumeByDate]
    total: int
    period: str  # "day", "week", "month"


class CategoryDistribution(BaseModel):
    """Category distribution item."""
    category: str
    count: int
    percentage: float
    supplier_id: Optional[str] = None  # For client-side filtering by supplier


class CategoryDistributionResponse(BaseModel):
    """Response for category distribution endpoint."""
    data: list[CategoryDistribution]
    total: int


class PagesStatsResponse(BaseModel):
    """Response for pages statistics."""
    total_documents: int
    total_pages: int
    avg_pages_per_fax: Optional[float] = None


class TimeOfDayDocument(BaseModel):
    """Document timestamp for time-of-day analysis."""
    timestamp: datetime
    supplier_id: Optional[str] = None  # For client-side filtering by supplier


class TimeOfDayVolumeResponse(BaseModel):
    """Response for time-of-day volume endpoint."""
    data: list[TimeOfDayDocument]
    total: int


# Response Models - Cycle Time
class CycleTimeByDate(BaseModel):
    """Cycle time metrics for a specific date."""
    date: date
    avg_minutes: float
    count: int
    supplier_id: Optional[str] = None  # For client-side filtering by supplier


class CycleTimeResponse(BaseModel):
    """Response for cycle time endpoint."""
    data: list[CycleTimeByDate]
    overall_avg_minutes: float
    metric_type: str  # "received_to_open" or "processing"


# Response Models - State Distribution
class StateDistributionItem(BaseModel):
    """Document state distribution item."""
    state: str
    label: str  # Display label (e.g., "Pushed", "Assigned")
    count: int
    percentage: float
    supplier_id: Optional[str] = None  # For client-side filtering by supplier


class StateDistributionResponse(BaseModel):
    """Response for state distribution endpoint."""
    data: list[StateDistributionItem]
    total: int


# Response Models - Productivity
class IndividualProductivity(BaseModel):
    """Productivity metrics for an individual."""
    user_id: str
    user_name: str
    total_processed: int
    avg_per_day: float
    median_minutes: Optional[float] = None
    supplier_id: Optional[str] = None  # For client-side filtering by supplier


class ProductivityResponse(BaseModel):
    """Response for productivity endpoint."""
    data: list[IndividualProductivity]
    total_processed: int
    unique_individuals: int


class CategoryByIndividual(BaseModel):
    """Category breakdown for an individual."""
    user_id: str
    user_name: str
    category: str
    count: int
    percentage: float
    supplier_id: Optional[str] = None  # For client-side filtering by supplier


class CategoryByIndividualResponse(BaseModel):
    """Response for category by individual endpoint."""
    data: list[CategoryByIndividual]


# Response Models - Supplier
class Supplier(BaseModel):
    """Supplier information."""
    supplier_id: str
    name: str
    ai_intake_enabled: bool


class SupplierListResponse(BaseModel):
    """Response for supplier list endpoint."""
    data: list[Supplier]
    total: int


class SupplierOrganization(BaseModel):
    """Supplier organization information."""
    organization_id: str
    name: str
    num_suppliers: int
    has_ai_intake: bool


class SupplierOrganizationListResponse(BaseModel):
    """Response for supplier organization list endpoint."""
    data: list[SupplierOrganization]
    total: int


# Response Models - Accuracy
class FieldAccuracy(BaseModel):
    """Accuracy metrics for a specific field.
    
    Accuracy = documents where initial system value matches final value (case-insensitive)
    """
    record_type: str
    field_identifier: str
    total_docs: int  # Total documents with system-preselected values for this field
    accurate_docs: int  # Documents where value didn't change
    accuracy_pct: float
    supplier_id: Optional[str] = None  # For client-side filtering by supplier


class PerFieldAccuracyResponse(BaseModel):
    """Response for per-field accuracy endpoint."""
    data: list[FieldAccuracy]
    overall_accuracy_pct: float
    total_fields: int


class DocumentAccuracyResponse(BaseModel):
    """Response for document-level accuracy endpoint."""
    total_ai_docs: int  # Total docs with system-preselected fields
    docs_with_edits: int  # Docs where at least one field changed
    docs_no_edits: int  # Docs where all fields match (accurate)
    accuracy_pct: float


class AccuracyTrendPoint(BaseModel):
    """Accuracy data point for a specific date."""
    date: date
    accuracy_pct: float
    total_docs: int  # Total documents for this period
    docs_with_changes: int  # Documents where values changed
    supplier_id: Optional[str] = None  # For client-side filtering by supplier


class AccuracyTrendResponse(BaseModel):
    """Response for accuracy trend endpoint."""
    data: list[AccuracyTrendPoint]
    overall_accuracy_pct: float
    period: str  # "day" or "week"


# Dashboard Summary
class DashboardSummary(BaseModel):
    """Summary metrics for the dashboard."""
    total_faxes: int
    total_processed: int
    avg_cycle_time_minutes: float
    ai_enabled_suppliers: int
    period_start: date
    period_end: date
