# Synthetic Test Data Rules

The generated data must be synthetic, plausible, and internally consistent.

## Privacy

- Do not use real personal data.
- Do not use real private email addresses.
- Do not use real phone numbers.
- Do not use real login credentials.
- Do not use real movement profiles of individual people.
- Names may sound realistic, but they must be fictional.
- Email addresses should use test domains such as `example.com`.

## Plausibility

The data should be consistent with factors such as:

- age
- life stage
- home location
- employment situation
- mobility preferences
- income or budget range
- weekday
- time of day
- season
- urban structure
- typical local mobility options
- travel statement or preferences

## Consistency

Pay special attention to internal consistency:

- A person without access to a car should not regularly drive their own car.
- A person with a significant remote-work share should not commute to the same workplace every day.
- Leisure activities should fit the person's life stage and home location.
- Trip chains must be temporally and spatially plausible.
- A trip must not have negative or unrealistic durations.
- Transport modes must fit the distance and urban context.
- Recurring patterns are allowed, but the generated data should not look mechanical or duplicated.

## Realism

Do not generate only ideal or perfectly clean data.

Realistic synthetic data may include:

- minor delays
- detours
- different transport modes
- weather- or time-dependent choices
- spontaneous leisure trips
- recurring routines
- occasional exceptions from normal behavior

## Limits

Avoid extreme or unlikely values unless explicitly requested.

Examples of patterns to avoid:

- too many trips on a single day
- unrealistically short travel times
- unrealistically long walking distances for everyday mobility
- daily long-distance travel without a clear reason
- perfectly even distribution of all transport modes
- exactly identical start times across many days
