# Experimental Protocol
## Securing Healthcare Chatbots Using LLM Firewalls

### 1. Research question

Does adding healthcare-aware output validation to an input/context defense reduce clinical harm from medical prompt injection, and what trade-offs does it introduce in benign response utility, false-positive refusals, and latency?

### 2. Hypothesis

The combined defense (D) will reduce attack success and high-severity clinical harm compared with input/context defense alone (B). It may increase latency or incorrectly block benign answers. These are hypotheses to test, not assumed results.

### 3. Dataset

- Benchmark: MPIB v1.2.
- Training split: 7,759 samples.
- Validation split: 969 samples.
- Test split: 969 samples.
- Preserve `sample_id`, `vector`, `scenario`, `labels`, and the original benchmark metadata.
- Use validation data for development and calibration.
- Reserve the test split for final evaluation.
- Follow the benchmark's official label and metric definitions.
- Do not redistribute functional payloads from the restricted registry.
- Do not use benchmark examples for real clinical decisions.

### 4. Configurations

A — Baseline: no external firewall.

B — Input/context defense: inspect user input and untrusted context before generation.

C — Output validation: generate a response, then validate it before release.

D — Combined defense: apply input/context defense and output validation.

Use the same samples, subject model, generation settings, and judging procedure wherever applicable. Record any unavoidable differences.

### 5. Primary security outcomes

- **Operational CHER:** calculate using the official MPIB convention, including severity-3 clinical-harm events.
- **Operational ASR:** calculate using the official MPIB convention, including severity-2 attack-success events.
- Report the benchmark's valid-only counterparts and JSON validity where applicable.

Do not redefine these metrics. Verify their denominators and handling of missing or invalid judge outputs against the official evaluator.

### 6. Utility and operational outcomes

- Benign false-positive refusal rate.
- Benign answer utility using a predefined, consistent rubric.
- End-to-end latency and output-validator overhead.
- Input-detector precision, recall, and F1 where reliable ground-truth labels support these calculations.
- Failure rate, including timeouts, malformed validator outputs, and unavailable inference services.

Define each denominator before running the final test.

### 7. Calibration and test isolation

Develop the detector and validator using development examples and validation data only.

Freeze prompts, thresholds, policies, model identifiers, and evaluation settings before test evaluation. Do not adjust the system in response to test-set results and then report those same results as an untouched final evaluation.

### 8. Data handling and logging

Log sample IDs, configuration, model and policy versions, decisions, metric-relevant outputs, latency, and failure status.

Keep restricted payloads out of Git, shared logs, and public artifacts. Do not send restricted data to an external inference provider until its data-use, retention, and applicable dataset terms have been checked.

### 9. Reporting

Report actual results, denominators, failures, and limitations. Include comparisons between B and D, with uncertainty estimates where feasible. Do not fabricate metrics or claim that the system is clinically validated.

### 10. Scope limitations

This is a research prototype, not a deployed medical product. The initial study focuses on text-based prompt injection and response validation. Real patient data, live EHR actions, and clinical deployment are out of scope.

### 11. Reproducibility

Record the dataset release, code commit, inference provider and model identifier, judge configuration, run date, random seeds where applicable, and all deviations from the planned protocol.