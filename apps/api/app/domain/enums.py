from enum import StrEnum


class LifecycleStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class VerificationStatus(StrEnum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    CONFLICTING = "conflicting"
    REJECTED = "rejected"


class EvidenceKind(StrEnum):
    DOCUMENT_REGION = "document_region"
    IMAGE_REGION = "image_region"
    SPREADSHEET_RANGE = "spreadsheet_range"
    IFC_OBJECT = "ifc_object"
    MANUAL_ASSERTION = "manual_assertion"
    DERIVED_VALUE = "derived_value"


class FactSource(StrEnum):
    MANUAL = "manual"
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    IFC = "ifc"
    DRAWING = "drawing"
    DERIVED = "derived"


class CheckStatus(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    NOT_APPLICABLE = "not_applicable"


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
