# User Trip Generation Prompt

## Task

Generate synthetic trip records for exactly one user in the mobility application test data pipeline.

A trip represents a complete movement from one meaningful origin to one meaningful destination, such as:

- home to work
- work to home
- home to grocery shopping
- home to a leisure activity
- gym to home
- home to a social visit
- home to another city
- another city to home

Do not generate detailed trip legs in this step. Trip legs will be generated separately later.

The generated trips must be plausible for the provided user profile, consistent with the user's available mobility subscriptions, and fall within the requested date range.

## Input Context

Use the following input context:

- User profile: `{{user_profile_json}}`
- User mobility subscriptions: `{{user_mobility_subscriptions_json}}`
- Start date: `{{start_date}}`
- End date: `{{end_date}}`
- Generate number of trips in the range: `{{num_trips}}`

## Generation Instructions

Generate a realistic sequence of trips for the given user between the start date and end date.

The trips should reflect the user's:

- home location
- life stage
- employment situation
- remote work share
- household situation
- mobility access
- mobility preferences
- avoided transport modes
- mobility constraints
- typical weekday behavior
- typical weekend behavior
- existing mobility subscriptions

The trips must form a plausible mobility history.

Do not create isolated random trips. Trips should make sense as part of a daily or weekly pattern.

## Subscription Awareness

Use the provided mobility subscriptions when deciding which transport modes are likely.

Examples:

- A user with a public transport subscription is more likely to use public transport regularly.
- A user with a bike sharing account may use bike sharing for short urban trips.
- A user with a car sharing account and a driving license may occasionally use car sharing for shopping, leisure, or weekend trips.
- A user with an e-scooter account may occasionally use e-scooters for short spontaneous trips.
- A user without a matching subscription may still use some services occasionally, but this should be less frequent and must remain plausible.
- A user without a driving license must not drive a car or use car sharing as the driver.

Do not force every subscription to appear in the generated trips.

## Temporal Scope

All generated trips must start and end within the requested date range.

Trips should be distributed realistically across the period.

Consider:

- weekdays
- weekends
- working days
- remote work days
- leisure time
- errands
- morning and evening routines
- occasional irregular behavior

Avoid generating trips at mechanically identical times every day.

## Output Requirements

Return exactly one JSON object.

The root object must contain the key `user_trips`.

The value of `user_trips` must be an array of trip objects.

Each trip object must strictly follow the provided output schema from the loaded prompt context.

Do not include any explanation, comments, Markdown, or text outside the JSON response.
