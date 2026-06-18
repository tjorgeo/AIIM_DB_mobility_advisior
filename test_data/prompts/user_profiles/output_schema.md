# User Profile Output Schema

The output must be a JSON object with the following root structure:

{
"user_profiles": [
{
"user_id": "string | UUID ",
"source_persona_id": "string",
"profile_variant": "string",
"generation_rationale": "string",

```
  "email": "string | null",
  "username": "string | null",
  "external_auth_id": "string | null",

  "first_name": "string",
  "last_name": "string",
  "display_name": "string",
  "date_of_birth": "YYYY-MM-DD",
  "age": "integer",
  "gender": "female | male | diverse | not_specified",
  "life_stage": "string",

  "home_city": "string",
  "home_postal_code": "string",
  "home_country_code": "string",
  "city_type": "string | null",

  "employment_status": "string | null",
  "occupation": "string | null",
  "work_city": "string | null",
  "work_postal_code": "string | null",
  "work_country_code": "string | null",
  "work_arrangement": "string | null",
  "remote_work_share": "number | null",

  "household_size": "integer | null",
  "household_type": "string | null",
  "income_band": "string | null",
  "mobility_budget_monthly_eur": "number | null",

  "has_driving_license": "boolean | null",
  "car_access": "none | occasional | shared | own | null",
  "bike_access": "none | occasional | own | shared | null",
  "public_transport_subscription": "none | monthly_pass | deutschlandticket | job_ticket | student_ticket | other | null",

  "preferred_transport_modes": ["string"],
  "avoided_transport_modes": ["string"],
  "mobility_constraints": ["string"],
  "typical_weekday_pattern": "string | null",
  "typical_weekend_pattern": "string | null",

  "travel_statement": "string",
  "activity_statement": "string"
}
```

]
}

## Important Notes

Do not generate fields that are not part of the active schema.

Do not omit required fields from the active schema.

Use `null` only for optional fields where no plausible value can be inferred.
