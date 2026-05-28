from src.forms import MedicalFormValidator
from src.schemas import MedicalFormValidationRequest, SymptomIntakeRequest
from src.symptoms import SymptomIntakeService


def test_symptom_intake_extracts_fields_and_red_flags():
    service = SymptomIntakeService()
    response = service.intake(
        SymptomIntakeRequest(
            session_id="demo",
            text="I have chest pain in my chest for 2 days, severity 8/10",
            structured={"medications": "aspirin", "allergies": "none"},
        )
    )

    assert response.captured["severity"] == 8
    assert response.triage_level == "urgent"
    assert any(flag.code == "chest_pain" for flag in response.red_flags)


def test_form_validator_returns_errors_and_normalized_fields():
    validator = MedicalFormValidator()
    response = validator.validate(
        MedicalFormValidationRequest(
            form_type="medicare_intake",
            fields={
                "full_name": "Jane Patient",
                "date_of_birth": "1950-01-02",
                "medicare_number": "1eg4te5mk73",
                "consent_to_contact": True,
            },
        )
    )

    assert response.is_valid is True
    assert response.normalized["medicare_number"] == "1EG4TE5MK73"


def test_form_validator_rejects_bad_severity():
    response = MedicalFormValidator().validate(
        MedicalFormValidationRequest(form_type="symptom_intake", fields={"primary_symptom": "pain", "duration": "today", "severity": 12})
    )

    assert response.is_valid is False
    assert any(error.field == "severity" for error in response.errors)
