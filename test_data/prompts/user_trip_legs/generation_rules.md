# Trip Leg Generation Rules

These rules apply specifically to trip-leg generation.

General synthetic data, privacy, plausibility, and realism rules are defined in the shared prompt files and must also be followed.

## Parent Trip Consistency

Every trip leg must be consistent with its parent trip.

For each parent trip:

- Generate at least one leg.
- Use the same `trip_id`.
- Use the same `user_id`.
- Keep all legs within the parent trip's time window.
- Do not create overlapping legs within the same trip.
- Preserve the overall origin and destination meaning.
- Preserve the overall trip purpose.
- Preserve the general mode choice from the parent trip.
- Preserve the approximate total duration, distance, and cost.

The first leg should start at the parent trip origin.

The last leg should end at the parent trip destination.

## Sequence Rules

Legs must form a logical sequence.

- `leg_sequence_number` starts at 1 for each trip.
- The destination of one leg should logically connect to the origin of the next leg.
- Transfer legs should only appear when they are plausible.
- Waiting time should be assigned to the leg where it is most meaningful, usually before a public transport or regional train leg.
- A simple trip should not be split into too many legs.

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

## Ticket related

If a user holds a subscription for the transport mode, show subscription.

Else show single_ticket for public_transport, regional_train and long_distance_train,
show pay-as-you go for car_sharing, bike_sharing, e_scooter
else none.

Select ticket_class according to users preferences.

## Mode-Specific Rules

### Walking

Walking legs are plausible for:

- short direct trips
- access to public transport
- egress from public transport
- access to car sharing, bike sharing, or e-scooter pickup
- short transfers

Walking legs should usually be short and low cost.

### Bicycle

Own bicycle legs are plausible for users with bike access and suitable mobility preferences.

Bicycle trips may consist of one direct leg or be part of an intermodal trip.

Provider name should usually be `null` for own bicycle legs.

### Bike Sharing

Bike-sharing legs should only be used when consistent with the user's subscriptions or the parent trip.

Bike-sharing legs are usually short to medium urban segments.

Provider name should match the user's bike-sharing subscription when available.

### Public Transport

Public transport trips often include:

- walking access leg
- one or more public transport legs
- optional transfer walking leg
- walking egress leg

Use generic but realistic service line names when appropriate, such as:

- U-Bahn
- S-Bahn
- Tram
- Bus

Do not create overly precise stop-level data unless the input context provides it.

Set ticket_type to single_ticket, if user has no Deutschlandticket is available.

### Regional Train and Long distance train

Regional train and long distance train legs are plausible for longer regional or cross-city trips.

They may include access and egress legs.

Use generic service line values such as `RE`, `RB`, `IC` or `ICE` where plausible.

Set ticket_type to single_ticket, if user has no Deutschlandticket is available.

Set ticket_class according to the users travel preferences, job industry and income.

### Car and Car Sharing

Car or car-sharing trips may include:

- walking access to parked vehicle or pickup point
- main driving leg
- walking egress from parking location to destination

A user without a driving license must not receive a car-sharing or driving leg as the main transport mode.

Provider name should match the user's car-sharing subscription for car-sharing legs.

### E-Scooter

E-scooter legs should usually be short urban legs.

They may appear as direct short trips or access/egress segments.

Provider name should match the user's e-scooter subscription when available.

### Taxi and Ride Hailing

Taxi and ride-hailing legs should be occasional.

They usually consist of one main leg.

They should have a positive estimated cost.

## Intermodal Rules

If the parent trip has `is_intermodal` set to `true`, generate multiple legs with at least two different transport modes.

If the parent trip has `main_transport_mode` set to `mixed`, generate a plausible multi-modal sequence.

If the parent trip is not intermodal, usually generate one leg or a simple access-main-egress structure.

Do not force intermodality into simple trips.

## Subscription and Provider Rules

Provider usage must be consistent with the user's subscriptions and the parent trip.

- Walking, own bicycle, and own car legs usually have `provider_name` set to `null`.
- Public transport, bike sharing, car sharing, and e-scooter legs may have a provider.
- Do not reference inactive, cancelled, expired, or paused subscriptions unless the leg date falls within a valid historical subscription period.
- Do not invent provider names.
- If the parent trip specifies `used_provider_name`, at least one relevant leg should use the same provider.

## Time and Duration Rules

Leg timing must be realistic.

- The first leg starts at or very close to the trip start time.
- The last leg ends at or very close to the trip end time.
- Access and egress legs should usually be short.
- Waiting times should be plausible and not excessive.
- Public transport transfers may include waiting time.
- Direct walking, cycling, taxi, or car trips should usually not include waiting time.

## Distance Rules

Leg distances must be plausible for the selected transport mode.

General guidance:

- Walking legs are usually short.
- E-scooter legs are usually short.
- Bike and bike-sharing legs are usually short to medium.
- Public transport legs can cover short, medium, or longer urban distances.
- Regional train legs should usually cover longer distances.
- Car and car-sharing legs can cover a wide range, but should remain plausible for the parent trip.

## Cost Rules

Leg costs must be plausible.

- Walking and own bicycle legs usually cost `0.0`.
- Public transport legs covered by an active subscription may cost `0.0`.
- Bike sharing, e-scooter, car sharing, taxi, and ride hailing legs usually have a positive estimated cost.
- Regional_train has `0.0` if the user has a Deutschlandticket, else estimate the cost appropriately.
- Long_distance_trains are usually more expensive, estimate the cost appropriately.
- First_class tickets are more expensive then second_class tickets.
- If the parent trip has a total estimated cost, the sum of leg costs should approximately match it.
- Do not assign costs to every access or transfer walking leg.
- Estimate the CO2 emissions of the leg.

## Spatial Rules

Do not generate exact street addresses.

Use meaningful but generic labels such as:

- home
- office
- supermarket
- gym
- university
- restaurant
- friend_home
- family_home
- transit_stop
- train_station
- airport
- bike_sharing_station
- car_sharing_pickup
- e_scooter_pickup
- parking_location
- shopping_area

City and country fields must remain consistent with the parent trip.

Postal codes may be `null` if no plausible value can be inferred.
