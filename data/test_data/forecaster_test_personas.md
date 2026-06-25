# Forecaster Agent — Test Personas

Use these payloads with `POST /api/forecaster/test` (or the FastAPI docs UI at `http://localhost:8000/docs`).

Each persona now uses `ics_text` — the raw iCalendar format. The forecaster parses it
internally and lets the LLM decide which events are transport-relevant before forecasting.

> **Tip:** In the FastAPI docs UI you can paste the ICS content directly into the `ics_text`
> field as-is (the UI handles escaping). In curl or Postman, replace every newline with `\n`.

Each persona exercises a different aspect of the forecaster:
- **Anna** — only local events in calendar → all filtered out → single baseline scenario
- **Max** — business trip + confirmed relocation → two scenarios
- **Lisa** — vague trip (low confidence) + internship start (medium confidence) → two scenarios

---

## Persona 1 — Anna, Urban Commuter (Frankfurt)

Anna's calendar only has local events (dentist, yoga). The LLM should filter all of them out,
leaving no transport-relevant signal. Expected result: **one baseline scenario**, stable demand.

**Calendar (ICS):**
```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Anna Test Calendar//EN
CALSCALE:GREGORIAN

BEGIN:VEVENT
SUMMARY:Zahnarzt
DTSTART:20260710T100000Z
DTEND:20260710T110000Z
LOCATION:Frankfurt, Zahnarztpraxis Müller
DESCRIPTION:Halbjährliche Kontrolle.
END:VEVENT

BEGIN:VEVENT
RRULE:FREQ=WEEKLY;BYDAY=TU,TH
SUMMARY:Yoga-Kurs
DTSTART:20260707T183000Z
DTEND:20260707T193000Z
LOCATION:Frankfurt, Yoga-Studio
DESCRIPTION:Wöchentliche Yogastunde in der Nähe.
END:VEVENT

END:VCALENDAR
```

**API request body:**
```json
{
  "analyst_summary": {
    "dominant_patterns": [
      {"mode": "public_transport", "avg_trips_per_month": 44, "avg_distance_km": 7.5},
      {"mode": "bike_sharing",     "avg_trips_per_month": 10, "avg_distance_km": 3.0},
      {"mode": "walking",          "avg_trips_per_month": 20, "avg_distance_km": 1.2}
    ],
    "detected_seasonality": "Slightly more bike usage in summer months, otherwise stable.",
    "current_contracts": ["Deutschlandticket (€49/mo)", "CallABike subscription (€6/mo)"],
    "detected_inefficiencies": []
  },
  "ics_text": "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Anna Test Calendar//EN\nCALSCALE:GREGORIAN\n\nBEGIN:VEVENT\nSUMMARY:Zahnarzt\nDTSTART:20260710T100000Z\nDTEND:20260710T110000Z\nLOCATION:Frankfurt, Zahnarztpraxis Müller\nDESCRIPTION:Halbjährliche Kontrolle.\nEND:VEVENT\n\nBEGIN:VEVENT\nRRULE:FREQ=WEEKLY;BYDAY=TU,TH\nSUMMARY:Yoga-Kurs\nDTSTART:20260707T183000Z\nDTEND:20260707T193000Z\nLOCATION:Frankfurt, Yoga-Studio\nDESCRIPTION:Wöchentliche Yogastunde in der Nähe.\nEND:VEVENT\n\nEND:VCALENDAR",
  "forecast_horizon_days": 90
}
```

**What to look for in the response:**
- Single `"baseline"` scenario — no calendar signal influenced the forecast
- `life_event_detected: false`
- Rationale should note that no transport-relevant calendar events were found
- High confidence on `public_transport` (44 trips/month, dominant pattern)

---

## Persona 2 — Max, Relocating Professional (Munich → Berlin)

Max's calendar has a confirmed business trip to Berlin and a relocation event.
Both are high-confidence and transport-relevant.
Expected result: **two scenarios** — baseline (Munich) + post-relocation (Berlin commute).

**Calendar (ICS):**
```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Max Test Calendar//EN
CALSCALE:GREGORIAN

BEGIN:VEVENT
SUMMARY:Geschäftsreise Berlin – Abschlusspräsentation
DTSTART:20260728T090000Z
DTEND:20260728T180000Z
LOCATION:Berlin, Alexanderplatz 1, 10178 Berlin
DESCRIPTION:Letzte Präsentation im Berliner Büro vor dem Umzug. ICE München → Berlin 06:58 gebucht.
END:VEVENT

BEGIN:VEVENT
SUMMARY:Umzug nach Berlin – neue Stelle ab September
DTSTART:20260810T080000Z
DTEND:20260810T200000Z
LOCATION:Berlin, Prenzlauer Berg, 10405 Berlin
DESCRIPTION:Umzugstag. Neue Stelle in Berlin ab 01.09.2026. Bisheriger Pendelweg nach München entfällt.
END:VEVENT

END:VCALENDAR
```

**API request body:**
```json
{
  "analyst_summary": {
    "dominant_patterns": [
      {"mode": "car_sharing",         "avg_trips_per_month": 18, "avg_distance_km": 12.0},
      {"mode": "public_transport",    "avg_trips_per_month": 25, "avg_distance_km": 9.0},
      {"mode": "long_distance_train", "avg_trips_per_month": 4,  "avg_distance_km": 280.0},
      {"mode": "e_scooter",           "avg_trips_per_month": 5,  "avg_distance_km": 3.5}
    ],
    "detected_seasonality": "No strong seasonal pattern detected.",
    "current_contracts": ["Deutschlandticket (€49/mo)", "Miles car sharing membership"],
    "detected_inefficiencies": [
      "Long-distance train trips (€280/month out-of-pocket) not covered by any subscription. A BahnCard 25 or 50 could reduce costs."
    ]
  },
  "ics_text": "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Max Test Calendar//EN\nCALSCALE:GREGORIAN\n\nBEGIN:VEVENT\nSUMMARY:Geschäftsreise Berlin – Abschlusspräsentation\nDTSTART:20260728T090000Z\nDTEND:20260728T180000Z\nLOCATION:Berlin, Alexanderplatz 1, 10178 Berlin\nDESCRIPTION:Letzte Präsentation im Berliner Büro vor dem Umzug. ICE München → Berlin 06:58 gebucht.\nEND:VEVENT\n\nBEGIN:VEVENT\nSUMMARY:Umzug nach Berlin – neue Stelle ab September\nDTSTART:20260810T080000Z\nDTEND:20260810T200000Z\nLOCATION:Berlin, Prenzlauer Berg, 10405 Berlin\nDESCRIPTION:Umzugstag. Neue Stelle in Berlin ab 01.09.2026. Bisheriger Pendelweg nach München entfällt.\nEND:VEVENT\n\nEND:VCALENDAR",
  "forecast_horizon_days": 90
}
```

**What to look for in the response:**
- Two scenarios: `"baseline"` + something like `"post_relocation"` or `"berlin_commute"`
- `life_event_detected: true`, relocation flagged as the life event type
- `recommend_re_evaluation_in_days` set (relocation is near-term, within the forecast window)
- Post-relocation scenario: car sharing demand may drop (Berlin has strong public transport), long-distance train to Berlin disappears, new local commute pattern emerges

---

## Persona 3 — Lisa, Student with Mixed Signals (Cologne)

Lisa's calendar has a vague Amsterdam trip (uncertain, no tickets booked) and an internship
starting in September that changes her commute. The LLM should treat Amsterdam as low confidence
and the internship as a medium-confidence life event.
Expected result: **two scenarios** — baseline + internship-adjusted.

**Calendar (ICS):**
```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Lisa Test Calendar//EN
CALSCALE:GREGORIAN

BEGIN:VEVENT
SUMMARY:Evtl. Kurztrip Amsterdam mit Freunden?
DTSTART:20260720T100000Z
DTEND:20260722T200000Z
LOCATION:Amsterdam, Niederlande
DESCRIPTION:Spontantrip nach Amsterdam, falls alle Zeit haben. Noch keine Tickets gebucht, sehr unsicher.
END:VEVENT

BEGIN:VEVENT
SUMMARY:Praktikumsstart – Kanzlei Innenstadt
DTSTART:20260901T090000Z
DTEND:20260901T180000Z
LOCATION:Köln, Innenstadt, 50667 Köln
DESCRIPTION:Erster Praktikumstag. Neuer Arbeitsweg: ca. 25 Min. mit Stadtbahn statt Campus-Fahrrad. Pendelstrecke ändert sich voraussichtlich für 3 Monate.
END:VEVENT

END:VCALENDAR
```

**API request body:**
```json
{
  "analyst_summary": {
    "dominant_patterns": [
      {"mode": "bike_sharing",     "avg_trips_per_month": 22, "avg_distance_km": 4.5},
      {"mode": "public_transport", "avg_trips_per_month": 30, "avg_distance_km": 6.0},
      {"mode": "walking",          "avg_trips_per_month": 25, "avg_distance_km": 1.5},
      {"mode": "regional_train",   "avg_trips_per_month": 6,  "avg_distance_km": 45.0}
    ],
    "detected_seasonality": "Strong increase in bike_sharing during April–September. Regional train spikes in holiday weeks.",
    "current_contracts": ["Deutschlandticket (€49/mo)"],
    "detected_inefficiencies": [
      "Bike sharing trips (avg 22/month) not covered by subscription. A Nextbike flat pass (€9/mo) could save ~€15/month."
    ]
  },
  "ics_text": "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Lisa Test Calendar//EN\nCALSCALE:GREGORIAN\n\nBEGIN:VEVENT\nSUMMARY:Evtl. Kurztrip Amsterdam mit Freunden?\nDTSTART:20260720T100000Z\nDTEND:20260722T200000Z\nLOCATION:Amsterdam, Niederlande\nDESCRIPTION:Spontantrip nach Amsterdam, falls alle Zeit haben. Noch keine Tickets gebucht, sehr unsicher.\nEND:VEVENT\n\nBEGIN:VEVENT\nSUMMARY:Praktikumsstart – Kanzlei Innenstadt\nDTSTART:20260901T090000Z\nDTEND:20260901T180000Z\nLOCATION:Köln, Innenstadt, 50667 Köln\nDESCRIPTION:Erster Praktikumstag. Neuer Arbeitsweg: ca. 25 Min. mit Stadtbahn statt Campus-Fahrrad. Pendelstrecke ändert sich voraussichtlich für 3 Monate.\nEND:VEVENT\n\nEND:VCALENDAR",
  "forecast_horizon_days": 90
}
```

**What to look for in the response:**
- Two scenarios: `"baseline"` + something like `"internship_period"` or `"new_commute"`
- Amsterdam trip should appear in `rationale` as a low-confidence signal but must NOT trigger a second scenario on its own
- `life_event_detected: true` due to the internship (changes commute pattern)
- Internship scenario: increased `public_transport` (Stadtbahn commute), reduced `bike_sharing` (campus cycling replaced by transit)
- `recommend_re_evaluation_in_days` should suggest re-checking around the internship start
