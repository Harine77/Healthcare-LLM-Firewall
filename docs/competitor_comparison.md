# Competitor Comparison: Healthcare LLM Firewalls

## 1. MPIB — Medical Prompt Injection Benchmark

##(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& c:\FYP-INITIAL\.venv\Scripts\Activate.ps1)

**Purpose:** Evaluate medical LLM robustness against direct prompt injection and indirect injection through retrieved context.

**Existing contribution:** Provides clinically grounded evaluation data and metrics including Attack Success Rate (ASR) and Clinical Harm Event Rate (CHER).

**Relevance to this project:** MPIB can support an evaluation of whether adding output validation reduces clinical harm, provided the selected models, labels, and evaluation procedure are compatible with the official benchmark.

**Limitation for our implementation:** The public toolkit is a minimal inference and metric utility, not a complete orchestration system for every experiment in the paper.

## 2. QFIRE — Healthcare-Aware Prompt Firewall

**Purpose:** Protect LLM applications using purpose-scoped input filtering and a configurable detector pipeline.

**Existing contribution:** Healthcare/PHI rules, allow/block enforcement, audit logging, and benchmark tooling.

**Relevance to this project:** Establishes that healthcare-aware input filtering and auditable firewall enforcement already exist.

**Difference to investigate:** Whether an independently enforced output validator adds measurable clinical-safety benefit under MPIB evaluation beyond input/context defenses.

## 3. LLM Firewall Using Validator Agent

**Purpose:** Add a validator agent to inspect generated responses and enforce security policies.

**Existing contribution:** Demonstrates an output-validation architecture that can complement input-level security.

**Evaluation limitation:** The paper acknowledges that it lacks systematic benchmark results, detailed ablations, and quantitative false-positive, false-negative, and latency measurements.

**Relevance to this project:** Motivates a controlled evaluation of output validation, but does not establish that our proposed approach is novel.

## Provisional research question

Does adding healthcare-aware output validation to an input/context defense reduce high-severity clinical harm on MPIB, and what trade-offs does it introduce in benign response utility, false-positive refusals, and latency?

## Proposed contribution

A reproducible research prototype and controlled comparison of four defense configurations, using benchmark-defined metrics and transparent reporting of actual results. Novelty remains provisional until the closest prior methods and evaluation protocols have been compared in sufficient detail.
