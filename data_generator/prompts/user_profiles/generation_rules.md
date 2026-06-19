# User Profile Generation Rules

## Age and Life Stage

Age, date of birth, life stage, household situation, and employment status must be consistent.

Examples:

- A student profile should usually have an age and life stage that fit student life.
- A retired profile should usually not have a full-time job.
- A profile with young children may have different mobility patterns than a single commuter.
- A person with a high remote-work share should not commute to the office every weekday.

## Location

Home city, postal code, and city type must be plausible.

## Employment and Daily Routine

Employment information should influence mobility behavior.

Consider:

- full-time work
- part-time work
- remote work
- hybrid work
- student life
- shift work
- self-employment
- unemployment
- retirement

Work arrangement and remote-work share must be consistent.

Examples:

- `remote_work_share` close to `0.0` means mostly on-site work.
- `remote_work_share` close to `1.0` means mostly remote work.
- Hybrid workers should have varied commuting patterns.
- Shift workers may travel outside typical peak hours.

## Mobility Access

Mobility access must be realistic and internally consistent.

Consider:

- driving license
- car access
- bike access
- public transport subscription
- mobility budget
- household situation
- city context

Examples:

- A person without a driving license should not have `car_access` set to `own` unless there is a clear household reason.
- A person with a Deutschlandticket is likely to use public transport regularly.
- A person living in a dense urban area may plausibly have no car.
- Bike access should influence short and medium-distance trips.

## Mobility Preferences

Preferred and avoided transport modes should fit the profile, especially the travel statement, activity statement, income and job industry.

Valid examples of transport modes include:

- walking
- bicycle
- public_transport
- regional_train
- long_distance_train
- car
- car_sharing
- ride_hailing
- taxi
- e_scooter
- bike_sharing

Avoid perfectly balanced or generic preferences.

Each profile should have recognizable but realistic mobility tendencies.

## Behavioral Realism

Profiles should support realistic downstream trip generation.

Include routine patterns, but avoid making users look mechanical.

Good profiles may include:

- regular commuting
- occasional leisure trips
- grocery shopping patterns
- sports or fitness activities
- social visits
- family-related trips
- errands
- weekend differences
- weather-sensitive mode choices

Avoid profiles where all decisions are extreme, perfectly optimized, or too uniform.

## Travel and Activity Statement

Each profile should have a unique travel and activity statement, that summarizes the travel and activity behavior in 2 to 4 sentences.
