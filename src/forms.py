import re
from datetime import date
from typing import Any, Dict, List

from .schemas import FieldError, MedicalFormValidationRequest, MedicalFormValidationResponse


FORM_REQUIREMENTS = {
    "medicare_intake": ["full_name", "date_of_birth", "medicare_number", "consent_to_contact"],
    "symptom_intake": ["primary_symptom", "duration", "severity"],
    "appointment_follow_up": ["patient_name", "preferred_contact", "follow_up_reason"],
}


class MedicalFormValidator:
    def validate(self, request: MedicalFormValidationRequest) -> MedicalFormValidationResponse:
        fields = {key: value for key, value in request.fields.items() if value not in ("", None)}
        required = FORM_REQUIREMENTS.get(request.form_type, FORM_REQUIREMENTS["medicare_intake"])
        errors: List[FieldError] = []
        warnings: List[str] = []

        for field in required:
            if field not in fields:
                errors.append(FieldError(field=field, message="This field is required."))

        if "date_of_birth" in fields and not self._is_iso_date(str(fields["date_of_birth"])):
            errors.append(FieldError(field="date_of_birth", message="Use YYYY-MM-DD format."))

        if "medicare_number" in fields:
            medicare_number = str(fields["medicare_number"]).strip().upper()
            fields["medicare_number"] = medicare_number
            if not re.fullmatch(r"[0-9A-Z]{11}", medicare_number):
                errors.append(FieldError(field="medicare_number", message="Expected an 11-character Medicare number."))

        if "severity" in fields:
            try:
                severity = int(fields["severity"])
                fields["severity"] = severity
                if not 1 <= severity <= 10:
                    errors.append(FieldError(field="severity", message="Severity must be between 1 and 10."))
            except (TypeError, ValueError):
                errors.append(FieldError(field="severity", message="Severity must be a number from 1 to 10."))

        if fields.get("consent_to_contact") is False:
            warnings.append("Patient did not consent to contact; reminder workflows should not send outbound messages.")

        return MedicalFormValidationResponse(
            is_valid=not errors,
            errors=errors,
            warnings=warnings,
            normalized=fields,
        )

    @staticmethod
    def _is_iso_date(value: str) -> bool:
        try:
            date.fromisoformat(value)
            return True
        except ValueError:
            return False
