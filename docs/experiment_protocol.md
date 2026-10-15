# Initial Experiment Protocol

## Primary research question
Does adding output validation to an input-side defense
reduce clinically harmful responses to medical
prompt-injection attacks?

## Experimental configurations

A. No external firewall
B. Input/context defense only
C. Output validator only
D. Input/context defense plus output validator

## Primary security outcome
Clinical-harm metric as defined by the selected benchmark.

## Secondary outcomes
- Attack success
- False-positive refusals on clearly benign questions
- Response utility
- End-to-end latency
- Incremental validator latency and model-call cost
- Validator and system failure rates

## Fair-comparison requirements
- Use the same underlying generation model wherever possible.
- Keep system instructions and decoding settings consistent.
- Use the same test examples for comparable configurations.
- Tune thresholds on development/validation data only.
- Freeze the test set and experimental settings before the
  final comparison.
- Record software versions, model IDs, configuration,
  sample IDs, decisions, timing, and failures.

## Reporting rule
No performance result will be claimed until the corresponding
experiment has completed and its output has been checked.