# Trip Leg Generation Prompt

## Task

Generate synthetic trip-leg records for the provided trips of exactly one user in the mobility application test data pipeline.

A trip leg represents one concrete segment of a larger trip.

Examples:

- walking from home to a transit stop
- taking a subway from one stop to another
- taking a regional_train or long_distance_train to another station
- walking from the destination stop to the office
- riding a bike-sharing bike from home to a shopping area
- driving a car-sharing vehicle from a pickup location to a supermarket
- using an e-scooter for a short urban segment

The input trips already describe complete movements from meaningful origins to meaningful destinations. Your task is to split these trips into realistic trip legs.

## Input Context

Use the following input context:

- User profile: `{{user_profile_json}}`
- User mobility subscriptions: `{{user_mobility_subscriptions_json}}`
- User trips: `{{user_trips_json}}`

## Generation Instructions

Generate trip legs for all provided trips.

Each generated leg must reference one existing `trip_id` from the input trips.

The trip legs must preserve the meaning, timing, main transport mode, origin, destination, distance, and cost assumptions of the parent trip.

Do not generate new trips.

Do not omit trips unless explicitly instructed.

Each parent trip must have at least one trip leg.

## Leg Granularity

Use realistic leg granularity.

Examples:

A walking trip may have one leg:

- walking from home to supermarket

A public transport trip may have multiple legs:

- walking from home to transit stop
- public transport from origin to station and repeat until the station is the destination stop
- walking from destination stop to office

An intermodal trip may have several legs:

- walking to bike-sharing station
- bike sharing to train station
- regional train or long distance train to another city
- regional train or long distance train from origin to station and repeat until the station is the destination stop
- walking to destination

A car-sharing trip may have legs such as:

- walking to car-sharing pickup location
- car sharing drive
- walking from parking location to destination

Do not over-split simple trips.

Do not create unnecessary micro-legs.

## Subscription Awareness

Use the provided mobility subscriptions when assigning providers.

Examples:

- A public transport leg may use an active public transport provider from the user's subscriptions.
- A bike-sharing leg may use an active bike-sharing provider from the user's subscriptions.
- A car-sharing leg may use an active car-sharing provider from the user's subscriptions.
- An e-scooter leg may use an active e-scooter provider from the user's subscriptions.
- Walking legs usually have no provider.
- Own bicycle or own car legs usually have no external provider.

Do not reference providers that are not present in the user's subscription input, unless the parent trip already explicitly references that provider.

## Output Requirements

Return exactly one JSON object.

The root object must contain the key `trip_legs`.

The value of `trip_legs` must be an array of trip-leg objects.

Each trip-leg object must strictly follow the provided output schema from the loaded prompt context.

Do not include any explanation, comments, Markdown, or text outside the JSON response.
