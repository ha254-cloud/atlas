from enum import StrEnum


class FinanceDataDimension(StrEnum):
    DEPARTMENT = "department"
    CLINICIAN = "clinician"


class ForecastMethod(StrEnum):
    OPEN_CASE_PROBABILITY_WEIGHTED = "open_case_probability_weighted"
