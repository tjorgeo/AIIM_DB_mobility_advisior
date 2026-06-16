# User Trip Generation Rules

These rules apply specifically to user trip generation.

General synthetic data, privacy, plausibility, and realism rules are defined in the shared prompt files and must also be followed.

## Subscription Consistency

Trips must be consistent with the user's mobility subscriptions.

- A trip using `public_transport` may reference an active public transport subscription.
- A trip using `bike_sharing` may reference an active bike sharing subscription or account.
- A trip using `car_sharing` may reference an active car sharing subscription or account.
- A trip using `e_scooter` may reference an active e-scooter subscription or account.
- If no matching subscription is used, set `used_subscription_category` to `none` and `used_provider_name` to `null`.
- Do not reference providers that are not present in the user's subscription input.
- Do not use inactive, cancelled, expired, or paused subscriptions unless the trip date falls within a valid historical subscription period.
- A user without a driving license must not make car-sharing trips as the driver.

## Temporal Consistency

Trips must be chronologically valid.

- All trips must fall within the requested date range.
- `started_at` must be earlier than `ended_at`.
- Trips for the same user must not overlap.
- Trips should follow a plausible daily sequence.
- A home-return trip should usually follow an earlier outbound trip.
- Commute trips should usually occur on working days unless the profile suggests weekend or shift work.
- Hybrid workers should not commute every weekday if their remote-work share is significant.
- Weekend trips should emphasize leisure, errands, shopping, family, or social purposes more than work commuting.

## Spatial Consistency

Trip origins and destinations must be spatially plausible.

- Home-based trips should usually start or end in the user's home city.
- Work trips should be consistent with the user's work city if a work city is provided.
- Cross-city trips are allowed only if they are realistic for the user and the region.
- Everyday trips should usually stay within the home city or nearby region.
- Do not generate precise street addresses.
- Use meaningful but generic location labels such as `home`, `office`, `supermarket`, `gym`, `university`, `restaurant`, `friend_home`, `doctor`, `train_station`, or `shopping_area`.

## Mode Choice

Transport mode must fit the user, distance, purpose, and subscriptions.

General guidance:

- Walking is plausible for short trips.
- Bicycle or bike sharing is plausible for short to medium urban trips.
- Public transport is plausible for regular urban travel and commuting.
- Regional train is plausible for longer regional trips or cross-city.
- Long distance train is plausible for longer cross-city trips and especially business trips.
- Car sharing is plausible for occasional shopping, leisure, family visits, or trips with bulky items.
- E-scooters are plausible for short spontaneous urban trips.
- Taxi or ride hailing should be occasional and not overused.
- `mixed` is allowed for trips that clearly combine multiple modes, but the detailed breakdown must still be left to the trip-leg generation step.

## Distance and Duration

Distance and duration must be realistic.

- Very short trips should not have very long durations unless there is a clear reason.
- Long distances should not have unrealistically short durations.
- Walking trips should usually be short.
- E-scooter trips should usually be short.
- Bike and bike-sharing trips should usually be short to medium distance.
- Public transport trips may be short, medium, or longer urban trips.
- Regional train trips should usually cover longer distances.
- Long distance train trips are usually cover longer distances.
- Car and car-sharing trips may be short to medium but should not dominate dense urban profiles unless justified.

## Behavioral Realism

The generated trip history should look realistic, not mechanical.

Include a mix of:

- routines
- commute trips
- errands
- grocery shopping
- leisure activities
- social visits
- family visits
- business trips
- cross-city leisure trips
- sports or fitness trips
- occasional spontaneous trips
- days with few trips
- days with no trips, if plausible for the requested period and number of trips

Avoid:

- identical trips every day at exactly the same time
- every trip using the same mode
- every subscription being used equally often
- too many trips per day
- unrealistic late-night or early-morning trips unless the profile supports them
- excessive long-distance travel without a clear reason
