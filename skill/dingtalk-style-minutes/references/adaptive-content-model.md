# Adaptive content model v3

The model is the single source for the overview, board, prose minutes, and chaptered transcript.

```json
{
  "schema_version": 3,
  "source": {"transcript_path": "...", "duration_seconds": 0, "language": "zh"},
  "overview": "One paragraph only.",
  "minutes": {
    "title": "Subject title",
    "subtitle": "Editorial spine",
    "content_type": "argument|tutorial|interview|meeting|lecture|story|review|mixed",
    "sections": [],
    "prose_sections": []
  },
  "chapters": []
}
```

## Section kinds

- `cards`: 2-6 parallel concepts. Each item has `id`, `title`, `bullets`, 1-4 semantic `emphasis` phrases found exactly once in its bullets, optional `tag`, `icon`, `takeaway`, and `source_segment_ids`.
- `key_points`: same schema as cards; use for takeaways or principles.
- `timeline` / `process`: 2-8 ordered steps with `title`, `bullets`, 1-4 semantic `emphasis` phrases, optional `takeaway`, and `source_segment_ids`.
- `comparison`: exactly 2 sides; use only for a real contrast between alternatives, positions, or before/after states. Two unrelated risks are not a comparison.
- `metrics`: 2-8 items with `label`, `value`, `note`, and `source_segment_ids`.
- `quotes`: 1-5 items with `quote` and `source_segment_ids`.
- `synthesis`: one `text` plus `source_segment_ids`.

Use 3-7 board sections. Do not choose kinds to fill a template. Pick the smallest set that exposes the recording's logic.

`emphasis` is editorial metadata, not automatic keyword guessing. Select decision-bearing numbers, mechanisms, named concepts, constraints, or actions that let a reader scan the body. The renderer keeps ordinary copy regular and renders only those spans bold in the section accent colour.

`prose_sections` is independent, scan-first editorial writing. Each has a content-driven `title` and 2-4 `points`. Every point contains one concise `claim`, 1-3 `details`, and `source_segment_ids`. A detail must contribute a fact, mechanism, example, constraint, or implication—not generic explanation. An optional section `callout` may state the final synthesis.

```json
{
  "title": "Why this mechanism works",
  "points": [
    {
      "claim": "A conclusion the reader can scan",
      "details": ["Evidence or mechanism that makes the claim true."],
      "source_segment_ids": ["seg-0001", "seg-0002"]
    }
  ]
}
```

The Feishu renderer expresses each topic as a heading, bold primary bullets, and nested evidence bullets. Never replace this hierarchy with consecutive essay paragraphs. It shares claims and evidence with the board, but regroups them for reading instead of expanding cards one by one or repeating card takeaways as headings.

## Chapter contract

Each chapter needs `title`, `start`, `end`, `summary`, and contiguous `segment_ids`. Chapters cover the full semantic transcript in chronological order without reordering. The Feishu transcript renders each as:

`【HH:MM:SS–HH:MM:SS】章节标题`

followed by one short summary and then every included source segment with its original timestamp and cleaned ASR text. Do not summarize away the verbatim transcript.
