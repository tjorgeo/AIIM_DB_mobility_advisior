from datetime import date

from profile_endpoint import ProfileOnboarding, ProfileUpdateRequest, _age_on, _unique_ids


def test_age_on_respects_birthday():
    born = date(2000, 8, 20)
    assert _age_on(born, date(2026, 8, 19)) == 25
    assert _age_on(born, date(2026, 8, 20)) == 26


def test_unique_ids_preserves_order_and_drops_blanks():
    assert _unique_ids(["a", "", "b", "a", "b"]) == ["a", "b"]


def test_connected_mobility_accounts_default_to_empty_list():
    onboarding = ProfileOnboarding()
    assert onboarding.connected_mobility_accounts == []


def test_incomplete_profile_allows_missing_optional_personal_data():
    request = ProfileUpdateRequest.model_validate({
        "user": {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
        },
        "onboarding": {},
    })
    assert request.user.date_of_birth is None
    assert request.user.home_city is None
    assert request.user.home_postal_code is None


def test_profile_update_contract_does_not_allow_subscription_changes():
    assert "active_subscription_ids" not in ProfileUpdateRequest.model_fields
    assert ProfileUpdateRequest.model_config["extra"] == "forbid"
