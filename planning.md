# Provenance Guard — Planning

## Detection signals

I'm going with the two signals the spec suggests, because honestly they're genuinely different approaches and I don't want to overthink signal selection when the real engineering challenge is combining and calibrating them.

**Signal 1: Groq LLM classification**

I ask llama-3.3-70b to read the text and estimate the probability it's AI-generated, returned as JSON like `{"ai_probability": 0.83, "reasoning": "..."}`. This is the "does this feel written by a machine" signal — it's picking up on argument structure, whether specifics feel earned or generic, voice consistency, that kind of thing.

Where it breaks: anything that's been "humanized" after generation — someone runs GPT output through a paraphraser or bolts on a personal anecdote — can slide right past this. It also has a bad habit of flagging non-native English speakers and people who write very formally, because careful/rule-following prose just looks like what an LLM produces.

**Signal 2: Stylometric heuristics**

Plain Python, no libraries. I'm computing sentence length variance, type-token ratio (vocabulary diversity), and punctuation density, then normalizing and averaging them into one score. AI text tends to be more uniform across these — human writing is messier.

Where it breaks: short text (under ~50 words) doesn't give you enough to compute reliable variance on. And it'll misread anyone writing simply and repetitively on purpose — kids' writing, some poetry, non-native speakers again.

**Combining them:**

`confidence = 0.6 * llm_score + 0.4 * stylometric_score`

I weighted the LLM signal higher because it's actually reasoning about meaning. The stylometric stuff is a good sanity check but it's a proxy — I don't trust it as much on its own.

## How I'm handling uncertainty

Confidence is 0–1, where 1 means "very confident this is AI." Here's where I landed on thresholds:

- 0.75 and up → high-confidence AI
- 0.35 and below → high-confidence human
- anything in between → uncertain

I did NOT split this down the middle at 0.5, and that's deliberate. The hint in the spec is right — telling a real human writer their work is AI-generated is a much worse mistake than the reverse. So I made the bar for calling something "AI" higher (0.75) and left the human bar more relaxed (0.35), so people don't get stuck in "uncertain" purgatory for writing that's obviously theirs.

I'll sanity-check this in Milestone 4 by running the four example inputs from the spec and printing both raw signal scores next to the combined one — if they're wildly disagreeing on something, that tells me one of the signals needs adjusting before I trust it.

## The three labels

Writing these out now so I'm not improvising UI copy later:

- **High-confidence AI:** "This content shows strong indicators of AI generation. Our system is highly confident in this assessment based on multiple analysis signals."
- **High-confidence human:** "This content shows strong indicators of human authorship. Our system found no significant markers of AI generation."
- **Uncertain:** "We're unable to confidently determine whether this content is AI-generated or human-written. Treat this classification as inconclusive."

## Appeals

Only the creator who submitted the content (matched by `creator_id`) can appeal it. They send `content_id` and `creator_reasoning` — basically, their side of the story.

When an appeal comes in:
1. Pull up the original record by `content_id`.
2. Flip status to `under_review`.
3. Log the appeal — timestamp, their reasoning, and a pointer back to the original decision (attribution, confidence, both raw scores).
4. Send back a confirmation.

No auto-reclassification. A human needs to actually look at it. If I were building the reviewer view, they'd want to see: the original text, the original label + confidence + both signal scores side by side, the creator's explanation, and the timestamps for both events.

## Where this will probably get it wrong

Two cases I'm expecting trouble with:

1. Short, repetitive poems — think children's verse or anything using simple language and repeated structure on purpose. Low vocabulary diversity + low sentence variance reads as "AI" to my stylometric signal even though it's clearly a human choice.
2. Formal writing from non-native English speakers, or anything academic/technical. Both signals struggle here — the LLM pattern-matches "careful phrasing" to AI, and the stylometric signal sees consistent sentence structure and reads it as machine-generated.

## Architecture

```
SUBMISSION
  POST /submit (text, creator_id)
    -> generate content_id
    -> Signal 1 (Groq) -> llm_score
    -> Signal 2 (stylometrics) -> stylometric_score
    -> combine -> confidence
    -> map confidence to label (0.75 / 0.35 thresholds)
    -> write audit log entry (everything above + status: classified)
    -> return { content_id, attribution, confidence, label }

APPEAL
  POST /appeal (content_id, creator_reasoning)
    -> look up original record
    -> status -> under_review
    -> write audit log entry (appeal reasoning + link to original decision)
    -> return confirmation
```

Basically: a submission runs through both signals independently, gets combined into one number, that number decides the label, and everything gets logged before the response goes out. An appeal doesn't touch the scoring at all — it just flags the record for a human to look at and logs why.

## AI tool usage plan

**M3:** I'll hand the AI tool the Signal 1 write-up above plus the submission diagram, and ask for the Flask skeleton + the Groq signal function. Before wiring it into the route, I'm testing the function on its own with a couple of throwaway strings to make sure the probability it returns actually makes sense.

**M4:** Same idea but with both signal sections plus the uncertainty/threshold section, asking for the stylometric function and the score-combining logic. I'll run the four spec example inputs through it and check the "clearly AI" one lands above 0.75 and the "clearly human" one lands below 0.35 — if not, I'm digging into which signal is off before moving on.

**M5:** Hand over the label text and appeals section plus the diagram, ask for the label function and the `/appeal` route. I'll force inputs through all three threshold ranges and check the label text matches word-for-word what's written above, then run an actual appeal end to end and confirm `GET /log` shows `under_review` with my reasoning attached.