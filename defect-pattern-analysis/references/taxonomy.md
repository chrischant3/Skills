# Defect taxonomy v1

## Defect type (what was wrong)
- function_logic: wrong algorithm, business rule or flow
- assignment_initialisation: wrong or missing default, state or variable value
- checking_validation: missing or wrong input validation, boundary or null handling
- interface_integration: contract mismatch between components, services or APIs
- timing_concurrency: race conditions, ordering, timeouts, retries
- data_config: bad data, migrations, feature flags, environment config
- build_package_deploy: pipeline, dependency, packaging or release issues
- ux_content: wrong copy, layout, accessibility, visual defects
- documentation: docs or help text wrong or missing

## Trigger (how it was found)
unit_test, integration_test, exploratory_test, code_review, monitoring_alert, production_incident, customer_report, internal_user

## Escape stage (earliest point it could reasonably have been caught)
refinement, design, development, code_review, automated_test, exploratory_test, release

## Rules
- One defect type per ticket. Pick the root cause, not the symptom.
- Confidence below 0.6 goes to unclassified, with a one-line reason (usually missing information, which is itself a clarity finding).
- Escape stage is about the system, never the person: "what in our process let it through".
