---
name: dingtalk-style-minutes
description: Use when supported Chinese audio, video, or an existing ASR transcript needs to become a DingTalk-style Feishu document with visual minutes, structured notes, speakers, chapters, and a complete timestamped transcript.
---

# DingTalk-style Minutes

Turn supported Chinese spoken media into a traceable Feishu document. Reproduce the information architecture users recognize from DingTalk AI Minutes—compress, structure, visualize, explain, preserve—without copying one recording's sections or relying on DingTalk APIs.

This is an independent skill inspired by the information architecture of DingTalk AI Minutes. It is not affiliated with or endorsed by DingTalk or Alibaba.

## Requirements

- Python 3.9-3.13 and network access.
- `clean-talking-video` installed as a sibling skill, or `CLEAN_TALKING_VIDEO_SKILL` set to its directory. Required only when starting from audio/video; existing `transcript.json` input can skip ASR.
- `DASHSCOPE_API_KEY` (or `DASHSCOPE_ASR_API_KEY`) for Qwen file transcription. Load it from an existing workspace `.ENV` when present; otherwise require it from the process environment. Never print it.
- Node.js 20+, npm/npx, `lark-cli`, an authenticated Feishu user, and permission to edit the destination document/whiteboard.
- Installed sub-skills listed below. Stop with an actionable missing-dependency or authorization message; do not silently skip ASR, the editable board, or live verification.

## Required sub-skills

- **REQUIRED SUB-SKILL:** Use `clean-talking-video` section 2 only for ASR.
- **REQUIRED SUB-SKILL:** Use `substance-writing-review` for the editorial spine and natural Chinese.
- **REQUIRED SUB-SKILL:** Use `beautiful-feishu-whiteboard` for SVG safety and live-board verification.
- Use `lark-doc` to create or surgically update the final document.

## Invariant Feishu contract

The document has exactly three top-level sections:

1. `一、内容概览` — one concise paragraph only. No lists, cards, metadata, or secondary headings.
2. `二、AI 纪要` — one adaptive editable whiteboard first, then scan-first editorial minutes. Each topic contains bold primary conclusions with nested facts, mechanisms, examples, or implications; it must not transcribe the board card-by-card or collapse into long essay paragraphs.
3. `三、完整转写` — `概述`, followed by semantic chapters formatted `【start–end】章节标题`, a one-paragraph chapter summary, and every timestamped source segment in chronological order.

Do not create a separate chapter-navigation section. Do not omit verbatim transcript segments.

## Workflow

1. Create an isolated work directory. Before any ASR call, load the workspace `.ENV` yourself when it exists: `set -a; source .ENV; set +a`. Otherwise use an already-set environment variable; never ask the user to paste or print a secret. Create a Python 3.9-3.13 virtual environment and install the `clean-talking-video` requirements when the work directory has no compatible environment.
2. For audio/video input, run `scripts/transcribe_media.py` with that virtual-environment Python. It delegates only to `clean-talking-video/scripts/transcribe.py`, uses `qwen-audio-3.0-asr-flash-filetrans`, enables speaker diarization by default, and produces `transcript.json` plus `draft.srt`. Supply `--speaker-count N` only when the likely count is known; use `--no-diarization` only for a clearly single-speaker recording. For an existing transcript, start at step 3.
3. Read the complete `transcript.json`. Preserve every `speaker_id`. Map anonymous speakers to real names only when self-introduction, participant metadata, or explicit handoff makes the identity reliable; otherwise retain `发言人 N`. Correct obvious ASR terms and remove failed takes only in a separate cleaned transcript; preserve timestamps and segment IDs. Never summarize from `draft.srt` alone.
4. Determine the dominant content type using [references/content-routing.md](references/content-routing.md). Read [references/editorial-aesthetics.md](references/editorial-aesthetics.md), then build schema v3 from [references/adaptive-content-model.md](references/adaptive-content-model.md):
   - one overview paragraph;
   - 3-7 content-driven board/minutes sections;
   - 2-7 independent editorial topics, each with 2-4 bold conclusions and 1-3 nested evidence details per conclusion;
   - chapter boundaries covering every transcript segment exactly once.
5. Choose each visual section by meaning: parallel concepts → cards; dependency → process; real contrast → comparison; decision-relevant figures → metrics; memorable exact language → quotes; integrated conclusion → synthesis. Never add a module merely for symmetry.
6. Attach `source_segment_ids` to every visual claim. No evidence-free cards, invented numbers, or unsupported conclusions. Build each important claim from the evidence with the highest explanatory gain: mechanism, example/counterexample, number/scale, named system, constraint/uncertainty, or causal link. This is editorial selection, not a global quota.
   Add 1-4 `emphasis` phrases to every card/process body. Choose only decision-bearing numbers, mechanisms, named concepts, constraints, or actions that already occur exactly once in the bullets; never bold whole paragraphs or guess emphasis at render time.
7. Run:

```bash
python scripts/lint_content_model.py content-model.json --transcript transcript.json
python scripts/render_graphic_minutes.py --input content-model.json --output graphic-minutes.svg
python scripts/validate_graphic_minutes.py graphic-minutes.svg --model content-model.json
npx -y @larksuite/whiteboard-cli@^0.2.11 -i graphic-minutes.svg -f svg --check
npx -y @larksuite/whiteboard-cli@^0.2.11 -i graphic-minutes.svg -o graphic-minutes.png -f svg
python scripts/render_feishu_document.py --model content-model.json --transcript transcript.json --output document.xml --whiteboard-token TOKEN
python scripts/validate_feishu_document.py document.xml --model content-model.json --transcript transcript.json --whiteboard-token TOKEN
```

8. View the PNG and run the multi-round review in [references/editorial-aesthetics.md](references/editorial-aesthetics.md). First judge independent readability, evidence strength, hierarchy, and whether the board feels specific to this recording; then fix layout. Treat content-driven height as a global layout contract: every ordinary card, key-point card, process/timeline row, comparison card, metric card, quote card, and synthesis card must derive its height from all visible title/body/takeaway lines. Cards in the same visual row may share that row's maximum required height for alignment; cards in different rows or sections must not inherit a fixed height. Reject unexplained vertical gaps between the final body line and takeaway/footer strip. Correct awkward wrapping, weak hierarchy, overflow, and content that looks like a generic slide template. If a supplied reference still has materially better information acquisition, revise the content grouping and evidence selection and render again; do not solve it by adding global count floors.
9. Write/update the Feishu whiteboard and document. If editing an existing document, preserve its current whiteboard token and resource blocks; move or replace only the required text blocks. Query the live PNG and raw nodes; verify editable text, colors, and layout.
10. Fetch the final document and verify the exact three-section contract, board/prose consistency, chapter summaries, timestamp order, and full transcript coverage.

## Content quality

- The overview answers “what is this recording fundamentally about?” in one paragraph.
- The board answers “what is the logic and what should I remember?”
- The board must pass the cover-the-transcript test: without prose or transcript, a reader can explain the core problem, claims, mechanism, and at least one concrete anchor. Information richness is a qualitative editorial preference, not a fixed count or word minimum.
- The editorial minutes answer “what are the primary conclusions, why are they true, how do they work, and what follows?” A reader should understand the hierarchy by scanning only headings and bold claims, then inspect nested details for evidence.
- Consecutive long paragraphs are a failed output form. Use `topic → bold claim → nested fact/mechanism/example/implication`; do not add filler just to make a point look developed.
- Never turn every board card into an `h3 + bullets` prose block. Board and prose are two editorial views over one evidence model.
- The transcript answers “what exactly was said and where?”
- Preserve exact figures, named mechanisms, dissent, uncertainty, and meaningful English terms.
- Delete generic phrases such as `提升效率`, `赋能`, or `底层逻辑` unless the speaker's exact phrasing is itself under discussion.
- Section titles state claims or concepts, not `背景介绍`, `主要内容`, or other empty labels.
- A board and prose section may share claims, but prose must add reasoning, context, or implications.

## Completion gate

Do not claim completion until:

- ASR output exists and duration is plausible;
- every visual claim has transcript provenance;
- every transcript segment appears in exactly one chapter;
- every diarized transcript segment carries a valid speaker ID and renders a speaker label;
- adaptive content lint and SVG validator pass;
- whiteboard check has no unexplained overflow/occlusion;
- local and live PNGs are visually inspected;
- the independent-readability and reference-comparison review has no obvious under-explained section;
- every card-like container is content-sized, with no fixed-height dead zone;
- live board contains editable text nodes;
- final Feishu document has exactly the three required top-level sections;
- an existing whiteboard/resource token remains present after document surgery;
- a forward test with a different content type produces a different, appropriate information architecture.
