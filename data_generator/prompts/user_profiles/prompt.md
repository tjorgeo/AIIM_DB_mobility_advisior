# User Profile Generation Prompt

## Task

Generate synthetic user profiles for the mobility application test data pipeline.

The profiles should represent realistic people who may use a mobility or trip-history application in an urban German context.

The generated profiles must be plausible, internally consistent, and suitable as input for later generation steps such as trips, trip legs, everyday activities, and mobility behavior.

## Input Context

Use the following input context when generating the profiles:

- Number of profiles to generate: `{{num_profiles}}`
- Target cities or regions: `{{target_locations}}`
- Persona seed definitions: `{{persona_seed_context}}`

## Generation Instructions

Create diverse synthetic user profiles.

Each profile should include enough information to support realistic downstream mobility generation, especially:

- where the person lives
- their life stage
- their employment situation
- their usual mobility options
- their mobility preferences
- relevant behavioral patterns
- travel and mobility preferences and avoidances
- constraints that influence daily travel behavior

Each profile must describe a coherent person.

## Diversity Requirements

Across the generated profiles, vary relevant characteristics such as:

- age
- gender
- household situation
- employment situation
- income or budget level
- mobility preferences
- car access
- bicycle access
- public transport usage
- remote work share
- weekday routines
- leisure behavior
- travel and mobility preferences

Avoid generating profiles that are too similar to each other.

## Output Requirements

Return exactly one JSON object.

The root object must contain the key `user_profiles`.

The value of `user_profiles` must be an array of profile objects.

Each profile object must strictly follow the provided output schema.

Do not include any explanation, comments, Markdown, or text outside the JSON response.
