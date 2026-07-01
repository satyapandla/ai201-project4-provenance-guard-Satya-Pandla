# ai201-project4-provenance-guard-Satya-Pandla
# Provenance Guard

A backend system that classifies submitted text as likely AI-generated, likely human-written, or uncertain — with a confidence score, a plain-language transparency label, an appeals path for contested classifications, rate limiting, and a structured audit log.

## Architecture Overview

A submission enters through `POST /submit` with `text` and `creator_id`. It's assigned a `content_id`, then passed independently through two detection signals: an LLM-based semantic classifier (Groq) and a set of stylometric heuristics (pure Python). Both scores are combined into a single confidence value, which is mapped to one of three transparency labels. Every step — both raw signal scores, the combined confidence, and the resulting label — is written to a structured audit log before the response returns.

If a creator disputes a classification, `POST /appeal` looks up the original decision by `content_id`, flips its status to `under_review`, and logs the appeal (with the creator's reasoning) alongside the original decision. No automated re-classification happens — a human is expected to review it.

```
SUBMISSION
  POST /submit (text, creator_id)
    -> generate content_id
    -> Signal 1 (Groq LLM) -> llm_score
    -> Signal 2 (stylometrics) -> stylometric_score
    -> combine (0.6 * llm_score + 0.4 * stylometric_score) -> confidence
    -> map confidence to label (thresholds: 0.75 / 0.35)
    -> write audit log entry
    -> return { content_id, attribution, confidence, label }

APPEAL
  POST /appeal (content_id, creator_reasoning)
    -> look up original record
    -> status -> under_review
    -> write audit log entry (appeal reasoning + link to original decision)
    -> return confirmation
```

## Detection Signals

**Signal 1 — Groq LLM classification (`llama-3.3-70b-versatile`).** Sends the text to Groq with a prompt asking it to estimate the probability the text is AI-generated, returned as structured JSON. This signal reasons about meaning — argument structure, specificity, voice consistency — rather than surface statistics. I chose it because it's the closest thing to "does this read like a machine wrote it" that's actually available without training a classifier from scratch.

*What it misses:* "humanized" AI output (paraphrased or edited after generation) can slip past it, and it tends to over-flag formal writing and non-native English speakers, since careful, rule-following prose pattern-matches to what LLMs produce.

**Signal 2 — Stylometric heuristics (pure Python, no libraries).** Computes three metrics — sentence length variance, type-token ratio (vocabulary diversity), and formal punctuation density — and averages them into one score. I picked this as the second signal specifically because it's structurally independent from Signal 1: one is semantic reasoning, the other is pure statistics on the text's shape.

*What it misses:* short text doesn't give these metrics enough data to be reliable (see Known Limitations below — I found this the hard way during testing, not by guessing).

**Combining them:**

```
confidence = 0.6 * llm_score + 0.4 * stylometric_score
```

LLM signal is weighted higher because it's actually reasoning about content, not just counting patterns. Stylometrics is a supporting signal, not a primary one.

## Confidence Scoring

Confidence is 0.0–1.0. Thresholds are **asymmetric on purpose**, but were recalibrated during testing (see Spec Reflection):

- `confidence >= 0.50` → high-confidence AI
- `confidence <= 0.35` → high-confidence human
- everything in between → uncertain

I originally set the AI threshold at 0.75. Testing against the four required example inputs showed that was too high — even the most obviously AI-generated test paragraph only reached 0.538, meaning "high-confidence AI" was never reachable in practice. I lowered the threshold to 0.50. It's still meaningfully harder to reach than the human threshold (0.35), preserving the core design goal — a false "this is AI" accusation is worse than the reverse — but it's now grounded in what the signals actually produce instead of a number I picked before I had real data.

**Real output from all four required test cases, run against the live system:**

| Input | llm_score | stylometric_score | confidence | Label reached |
|---|---|---|---|---|
| clearly_ai ("Artificial intelligence represents a transformative paradigm shift...") | 0.8 | 0.145 | **0.538** | likely_ai |
| clearly_human ("ok so i finally tried that new ramen place...") | 0.2 | 0.084 | **0.154** | likely_human |
| borderline_formal_human ("The relationship between monetary policy and asset price inflation...") | 0.8 | 0.213 | **0.565** | likely_ai |
| borderline_edited_ai ("I've been thinking a lot about remote work lately...") | 0.4 | 0.254 | **0.342** | likely_human |

Also observed live, in an earlier system run: a short, unambiguously human-written description ("The sun dipped below the horizon...") produced `confidence: 0.423`, landing as **uncertain** — the third label, demonstrated with real data, not synthetic testing.

Notably, `borderline_formal_human` — genuine academic prose about monetary policy — landed as `likely_ai`. That's not a bug I'm hiding; it's a live demonstration of a limitation I anticipated in planning.md before I ever ran the system: formal, careful writing gets over-flagged by both signals. See Known Limitations.

## Transparency Label

The exact text returned for each of the three classification outcomes:

- **High-confidence AI:** "This content shows strong indicators of AI generation. Our system is highly confident in this assessment based on multiple analysis signals."
- **High-confidence human:** "This content shows strong indicators of human authorship. Our system found no significant markers of AI generation."
- **Uncertain:** "We're unable to confidently determine whether this content is AI-generated or human-written. Treat this classification as inconclusive."

## Appeals Workflow

Only the original `creator_id` on a submission can appeal it. They provide `content_id` and `creator_reasoning`. On receipt, the system:

1. Looks up the original classification record.
2. Sets status to `under_review`.
3. Logs the appeal — timestamp, reasoning, and a pointer back to the original attribution, confidence, and both raw signal scores.
4. Returns a confirmation.

No automatic re-scoring. A reviewer opening the appeal queue would see the original text, the original label/confidence/signal breakdown, the creator's explanation, and both timestamps side by side.

**Verified real output** — appeal submitted against a real classification:

```json
{
  "appeal_reasoning": "I wrote this myself from personal experience.",
  "content_id": "55d96344-265e-4df0-b05e-2c391802ce60",
  "original_attribution": "uncertain",
  "original_confidence": 0.423,
  "original_llm_score": 0.4,
  "original_stylometric_score": 0.458,
  "status": "under_review"
}
```

## Rate Limiting

`10 per minute; 100 per day` on `POST /submit`, via Flask-Limiter with in-memory storage.

**Reasoning:** 10/minute reflects realistic usage for a single writer submitting or revising their own work in one sitting — nobody legitimately submits faster than that. 100/day allows for iterating on multiple pieces across a session without opening the door to sustained scripted abuse.

**Verified evidence** — 12 rapid requests against a live local server:

```
200
200
200
200
200
200
200
200
200
200
429
429
```

First 10 succeeded, remaining 2 were correctly rejected.

## Audit Log

Structured JSON, one entry per event. Captures timestamp, content ID, creator ID, attribution, confidence, both individual signal scores, and status. Appeal entries additionally capture `appeal_reasoning` and a pointer back to the original decision. Sample (real, from a live run):

```json
{
  "content_id": "55d96344-265e-4df0-b05e-2c391802ce60",
  "creator_id": "test-user-1",
  "attribution": "uncertain",
  "confidence": 0.423,
  "llm_score": 0.4,
  "stylometric_score": 0.458,
  "status": "classified",
  "timestamp": "2026-07-01T04:24:20.599559+00:00"
}
```

## Known Limitations

**1. Formal, careful writing scores as AI-generated — confirmed with real data, not just a hypothesis.** `borderline_formal_human`, a genuine piece of academic-register human writing about monetary policy, produced `confidence: 0.565` and was classified `likely_ai`. Both signals contribute to this: the LLM signal scored it 0.8 (pattern-matching formal phrasing to typical LLM output), and the stylometric signal's low variance/low diversity reading of careful, structured prose pushed the combined score further toward "AI." This is exactly the blind spot I flagged in planning.md before building anything — seeing it reproduce in a live test confirms it's a real property of the system, not a theoretical concern.

**2. Short, ordinary human writing scores as "uncertain" instead of "likely human."** A two-sentence, unambiguously human-written description ("The sun dipped below the horizon...") produced `confidence: 0.423` — uncertain, not human. At only ~30 words and 2 sentences, my stylometric sub-metrics don't have enough data to compute meaningfully and fall back to a neutral 0.5 default (a threshold I raised mid-build after an earlier version gave misleading results — see AI Usage). That leaves the LLM signal doing most of the work, and it's moderately, not extremely, confident on plain descriptive prose. Short-form content will systematically under-perform toward "uncertain" regardless of how clearly human it is.

**3. Short, repetitive, simple-vocabulary writing (e.g., children's poetry) will likely score as AI-like.** My stylometric signal treats low vocabulary diversity and uniform sentence structure as AI markers — but plenty of human writing is intentionally simple and repetitive. The signal can't distinguish "AI produced uniform text" from "a human chose to write uniform text on purpose."

**If deploying for real:** I'd want a labeled dataset of known human/AI text to calibrate thresholds and weights properly instead of the values I picked and then hand-corrected here, and a third signal that isn't as vulnerable to formal-writing false positives as both of my current signals turned out to be.

## Spec Reflection

**How the spec helped:** Writing out the exact three label strings in `planning.md` before building anything meant I never had to improvise label copy under time pressure during Milestone 5 — the label function was a straight lookup against text I'd already committed to.

**Where implementation diverged:** Two things, both discovered through the testing the spec explicitly required rather than guessed at beforehand. First, my original stylometric thresholds (variance computed from as few as 2 sentences, TTR from as few as 10 words) produced misleading scores on short excerpts — a genuinely AI-generated 2-sentence paragraph scored as "human-like" purely from having too little data, so I raised the minimums to 3 sentences and 40 words. Second, and more significant: my original AI-confidence threshold of 0.75 turned out to be unreachable — even the spec's own "clearly AI-generated" example only scored 0.538 against my real signals, meaning the `likely_ai` label would never fire in practice. I lowered the threshold to 0.50 after running the four required test cases and seeing this directly. Both changes exist because I tested against real inputs before considering the milestone done, exactly as instructed.

## AI Usage

**Instance 1 — Signal 2 + confidence scoring (Milestone 4).** I directed the AI tool to generate the stylometric signal function and the score-combining logic, based on my `planning.md` detection-signals and uncertainty sections. The first version used low data thresholds (2 sentences, 10 words) before trusting its sub-metrics. When I tested it against the four required example inputs, it produced a nonsensical result — a clearly AI-generated paragraph scored as "low AI-likelihood" on the variance sub-metric purely due to insufficient sentence count. I had the thresholds revised to require at least 3 sentences and 40 words before trusting the sentence-variance and TTR metrics respectively, falling back to neutral 0.5 otherwise.

**Instance 2 — Rate limiting (Milestone 5).** I directed the AI tool to add Flask-Limiter to the `/submit` route per the spec's documented setup pattern (in-memory storage, `10 per minute;100 per day`). I verified this myself by running a live 12-request burst against my running server and confirmed 10 successes followed by 2 rejections — the exact behavior documented in the Rate Limiting section above — before accepting it as correct.

**Instance 3 — Threshold recalibration (Milestone 6).** After writing the README, I ran the four required test cases against my live system and found the AI-confidence threshold (0.75, set in Milestone 2 before I had any real data) was unreachable — even the spec's "clearly AI-generated" example only scored 0.538. I directed the AI tool to lower the threshold to 0.50. I verified this by re-running the same four test scores against the new threshold and confirming `likely_ai` now fires correctly, and that the change didn't accidentally break the human-side classification of the clearly-human example.

## Portfolio Walkthrough

[Link to video]
