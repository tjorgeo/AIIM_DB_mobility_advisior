# User Mobility Subscription Generation Rules

These rules apply specifically to mobility subscription generation.

General synthetic data, privacy, plausibility, and realism rules are defined in the shared prompt files and must also be followed.

## User Consistency

Subscriptions must fit the user profile.

Consider:

- home city
- age
- life stage
- income band
- employment status
- remote work share
- car access
- bike access
- public transport subscription
- preferred transport modes
- avoided transport modes
- mobility constraints
- typical weekday and weekend patterns

## Public Transport

Public transport subscriptions are especially plausible for users who:

- live in dense urban areas
- commute regularly
- do not own a car
- have a student, job, or monthly transport ticket
- prefer public transport
- have a limited but stable monthly mobility budget

Do not assign a public transport subscription if the user profile clearly avoids public transport.

## Bike Sharing

Bike sharing is plausible for users who:

- live in dense urban areas
- use public transport and need first-mile or last-mile mobility
- do not own a bike
- are comfortable cycling
- make short urban trips
- have occasional leisure or errand trips

Bike sharing is less plausible for users with strong cycling constraints or very low use of active mobility.

## Car Sharing

Car sharing is plausible for users who:

- have a driving license
- do not own a car
- live in an urban area where car ownership is less necessary
- occasionally need a car for shopping, leisure trips, family visits, or weekend travel
- have sufficient income or mobility budget

A user without a driving license should not receive a car-sharing subscription.

## E-Scooter Sharing

E-scooter usage is plausible for users who:

- live in dense urban areas
- are younger or middle-aged
- make short spontaneous trips
- combine public transport with micro-mobility
- are not strongly constrained in terms of balance, safety, or mobility limitations

E-scooter subscriptions or accounts should usually be occasional rather than the primary mobility option.

## Temporal Consistency

Dates must be plausible.

- `valid_from` must not be after `valid_until`.
- Active subscriptions should usually have no `valid_until` or a future `valid_until`.
- Expired or cancelled subscriptions should have a past `valid_until`.
- `valid_from` should be plausible relative to the user's age and life situation.
- Do not create subscriptions that started before the user was old enough to use the service.

## Cost Consistency

Costs must be plausible.

- Public transport subscriptions often have a monthly cost.
- Car sharing may have a monthly fee, yearly fee, or pay-as-you-go account.
- Bike sharing may have a monthly plan, yearly plan, or pay-as-you-go account.
- E-scooter sharing is often pay-as-you-go or based on app usage.
- `monthly_cost_eur` should fit the billing cycle and subscription type.
- If `billing_cycle` is `pay_as_you_go` or `none`, `monthly_cost_eur` may be `null` or a plausible average monthly cost.

## Avoid Mechanical Patterns

Do not generate identical subscriptions for all users.

Vary:

- provider
- subscription type
- usage frequency
- status
- cost
- start date
- whether the subscription is a primary mobility option
