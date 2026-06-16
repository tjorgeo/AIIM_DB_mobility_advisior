# User Mobility Subscription Generation Prompt

## Task

Generate synthetic mobility subscription records for existing users in the mobility application test data pipeline.

The generated records should describe which mobility subscriptions, memberships, or service accounts a user currently has or plausibly had in the past.

Relevant mobility categories are:

- public transport
- bike sharing
- car sharing
- e-scooter sharing

The generated subscriptions must be plausible for each user profile, internally consistent, and restricted to the providers listed in the provider catalog.

## Input Context

Use the following input context:

- User profiles: `{{user_profiles_json}}`

## Generation Instructions

Generate subscription records for the provided users.

Do not assign every user every possible subscription. The number and type of subscriptions should depend on the user's mobility preferences, city, age, income band, household situation, employment situation, and transport access.

A user may have:

- no mobility subscription
- only a public transport subscription
- public transport plus bike sharing
- car sharing without owning a car
- occasional e-scooter usage through an app account
- multiple mobility accounts if this fits the profile

Each generated subscription must reference an existing `user_id` from the input user profiles.

## Provider Restrictions

Only use providers listed in the provider catalog.

Do not invent additional providers.

Provider category and provider name must match the provider catalog exactly.

If a provider is only available in certain cities, assign it only to users whose home city or relevant travel context makes that provider plausible.

## Output Requirements

Return exactly one JSON object.

The root object must contain the key `user_mobility_subscriptions`.

The value of `user_mobility_subscriptions` must be an array of subscription objects.

Each subscription object must strictly follow the provided output schema from the loaded prompt context.

Do not include any explanation, comments, Markdown, or text outside the JSON response.
