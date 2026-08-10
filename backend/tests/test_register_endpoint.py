import pytest
from pydantic import ValidationError

from register_endpoint import (
    OnboardingCompletionRequest,
    RegisterRequest,
    _has_onboarding_data,
)


def _minimal_registration(password="correct-horse"):
    return {
        "user": {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
        },
        "credentials": {"password": password},
    }


def test_minimal_registration_contract_defaults_to_empty_onboarding():
    request = RegisterRequest.model_validate(_minimal_registration())
    assert request.user.date_of_birth is None
    assert request.user.home_city is None
    assert request.onboarding.preferred_transport_modes == []
    assert request.subscriptions == []
    assert not _has_onboarding_data(request.onboarding, request.subscriptions)


def test_registration_requires_a_real_password():
    with pytest.raises(ValidationError):
        RegisterRequest.model_validate(_minimal_registration("short"))


def test_optional_onboarding_can_be_submitted_after_registration():
    request = OnboardingCompletionRequest.model_validate({
        "user": {"home_city": "Berlin", "home_postal_code": "10115"},
        "onboarding": {
            "preferred_transport_modes": ["public_transport"],
            "mobility_budget_monthly_eur": 120,
        },
    })
    assert request.user.home_city == "Berlin"
    assert request.onboarding.mobility_budget_monthly_eur == 120
