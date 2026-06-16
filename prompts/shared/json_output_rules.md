# JSON Output Rules

The response must contain valid JSON only.

## Strict Rules

- Do not output Markdown code blocks.
- Do not output explanatory text before or after the JSON.
- Do not include comments in the JSON.
- Use double quotes for all JSON keys and string values.
- Use `null` when an optional value is unknown or cannot be reasonably inferred.
- Do not use placeholders such as `"N/A"`, `"unknown"`, or `"tbd"` unless the schema explicitly requires those values.
- Do not use trailing commas.
- Output date values in `YYYY-MM-DD` format.
- Output timestamps in ISO 8601 format.
- Use a period as the decimal separator for numbers.
- Output IDs as strings unless the schema explicitly defines another type.

## Field Rules

- All required fields from the schema must be present.
- Field names must exactly match the schema.
- Do not generate additional fields unless the schema explicitly allows them.
- Data types must exactly match the schema.
- Arrays must be output as arrays, even if they contain only one item.
- Empty arrays are allowed when they are meaningful and permitted by the schema.
- Nested objects must be fully structured according to the schema.

## Consistency Rules

- Values that logically depend on each other must be consistent.
- Temporal sequences must be valid.
- Start times must be earlier than end times.
- Reference IDs must be reused consistently.
- If an object references another object, the referenced ID must either exist in the generated output or be provided in the input context.
