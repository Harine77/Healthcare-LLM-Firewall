# Project documents

Start with the [Mentor Review Guide](MENTOR_REVIEW_GUIDE.md) for a short explanation of the project, its terms, and what the current results do and do not show.

## Choose a document

- [Learning guide](learning.md): end-to-end explanation for understanding the code.
- [Architecture design](ARCHITECTURE_DESIGN.md): system diagram and request/evaluation flow.
- [Review handover](REVIEW_HANDOVER.md): implementation details, inspected result files, limitations, and current research status.
- [Experimental protocol](experimental_protocol.md): planned dataset split, configurations, and analysis method.
- [Threat model](thread_model.md): security scope and assumptions.
- [Competitor comparison](competitor_comparison.md): project comparison notes; cited claims still need primary-source review.

The two protocol files overlap. Treat `experimental_protocol.md` as the primary protocol and `experiment_protocol.md` as an older working note until they are reconciled.

## Live demo

Run `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`, then open `http://127.0.0.1:8000`. The page sends one request to `POST /evaluate` and displays that request's result. It is a research demo, not a clinical tool. Use synthetic, non-sensitive text.
