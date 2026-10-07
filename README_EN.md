[简体中文](README.md) | [English](README_EN.md)

# DingTalk-style Minutes

Turn a phone recording, meeting, or interview into an **editable Feishu document in the style of DingTalk AI Minutes**.

**One recording → overview + graphic minutes + chaptered full transcript**

<table>
  <tr>
    <td width="33%"><a href="examples/sections/01-ai-board.jpg"><img src="examples/sections/01-ai-board.jpg" alt="AI minutes whiteboard"></a><br><strong>AI minutes · board</strong></td>
    <td width="33%"><a href="examples/sections/02-ai-notes.jpg"><img src="examples/sections/02-ai-notes.jpg" alt="AI minutes text"></a><br><strong>AI minutes · text</strong></td>
    <td width="33%"><a href="examples/sections/03-transcript.jpg"><img src="examples/sections/03-transcript.jpg" alt="Full transcript"></a><br><strong>Full transcript</strong></td>
  </tr>
</table>

## Just tell the AI

```text
Use $dingtalk-style-minutes to turn this recording into a Feishu document.
```

## Installation and runtime requirements

The repository root contains project documentation; the installable Skill is in [`skill/dingtalk-style-minutes/`](skill/dingtalk-style-minutes/). Ask the Agent to check all dependencies:

```text
Install github.com/PoetCoderJun/dingtalk-style-minutes,
install github.com/zarazhangrui/beautiful-feishu-whiteboard,
install github.com/larksuite/cli and check that lark-doc / lark-shared Skills are available.
Authenticate a Feishu user and confirm edit access to the target document and whiteboard.
For DashScope, also install github.com/PoetCoderJun/clean-talking-video,
install its requirements.txt in an isolated Python environment, and configure DASHSCOPE_API_KEY.
For FunASR, install the selected model and dependencies in an isolated environment,
then normalize its output to transcript.json.
```

- Python 3.9–3.13; the DashScope audio proxy also requires FFmpeg / FFprobe.
- Node.js 20+, npm/npx for whiteboard checks and rendering; Feishu CLI, an authenticated user and editable targets.
- `beautiful-feishu-whiteboard` handles SVG and live-board verification; `lark-doc` and its shared dependencies handle documents. Installing the CLI does not establish that these Skills are available.
- `requirements-dev.txt` contains test dependencies. It does not install ASR models, clean-talking-video, the Feishu CLI or its Skills.

## Choose an input path

| Path | Actual dependency and boundary |
| --- | --- |
| Existing `transcript.json` | Skip ASR; preserve `id`, `start`, `end`, `text` in `segments`, and `speaker_id` when reliable diarization exists |
| DashScope | `transcribe_media.py` delegates to the clean-talking-video transcriber; requires a key, network access and that transcriber's Python dependencies |
| Local FunASR | The Agent installs a model, runs it and normalizes the result; this repository does not bundle a one-command FunASR adapter, and initial model downloads may need network access |

**Current public-version compatibility:** the clean-talking-video transcriber defaults to `qwen3-asr-flash-filetrans` (overridable with `DASHSCOPE_ASR_MODEL`), but does not accept `--diarization` or `--speaker-count` or produce `speaker_id`. This repository's wrapper requests diarization by default, so its default invocation fails with that dependency. Use `--no-diarization` only for clearly single-speaker recordings. For multiple speakers, supply a reliably diarized transcript or use a local model that supports diarization; the single-speaker path is not multi-speaker support.

This example is for a clearly single-speaker recording after dependencies and a key are configured. It calls a cloud service and may incur charges:

```bash
python <minutes-skill-root>/scripts/transcribe_media.py \
  --input /data/recording.m4a \
  --output-dir /work/minutes-demo \
  --clean-talking-skill /path/to/clean-talking-video/clean-talking-video \
  --no-diarization
```

`--clean-talking-skill` or `CLEAN_TALKING_VIDEO_SKILL` must point to the installed directory containing `scripts/transcribe.py`, which may not be the repository root. Without an override, the entry point checks common Codex / Agents Skills directories. It writes `transcript.json` and `draft.srt`; follow the [Skill workflow](skill/dingtalk-style-minutes/SKILL.md) using the complete JSON, not the SRT alone.

## Where data goes

The DashScope path creates a compressed audio proxy locally, then uploads it to DashScope temporary storage for recognition. It does not upload the original video. FunASR or an existing transcript can skip cloud ASR, but the chosen Agent service may still process transcript text.

Delivery writes minutes, the complete transcript and the whiteboard to Feishu, then reads the live board and document for verification. Local FunASR describes the transcription location, not a fully local workflow. If upload is unavailable, stop at local modeling / rendering; those artifacts are not a completed Feishu delivery.

## Inspect evidence and validate

The three images above are [existing output previews](examples/sections/), not a complete replayable recording case. Public engineering evidence includes source-segment links, transcript coverage checks, SVG and document validators, and [local fixtures](tests/fixtures/). These do not establish client deployments or business results.

Development checks require an isolated environment and test dependencies:

```bash
python3 -m venv ../.venv-minutes
../.venv-minutes/bin/python -m pip install -r requirements-dev.txt
../.venv-minutes/bin/python -m unittest discover -s tests -v
```

Keep the virtual environment outside the repository so package checks do not treat dependency bytecode as release content. These tests require no API keys and do not write to Feishu. Live-board and final-document verification remain delivery steps.

## License

[MIT](LICENSE). Inspired by the information structure of DingTalk AI Minutes. Not affiliated with DingTalk or Alibaba.
