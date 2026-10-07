[简体中文](README.md) | [English](README_EN.md)

# DingTalk-style Minutes

手机录音、会议录音、采访音频，都能变成一份**钉钉闪记风格的飞书图文纪要**。

**一段录音 → 内容概览 + AI 图文纪要 + 分章节完整转写**

<table>
  <tr>
    <td width="33%"><a href="examples/sections/01-ai-board.jpg"><img src="examples/sections/01-ai-board.jpg" alt="AI 纪要画板"></a><br><strong>AI 纪要 · 画板</strong></td>
    <td width="33%"><a href="examples/sections/02-ai-notes.jpg"><img src="examples/sections/02-ai-notes.jpg" alt="AI 纪要文字"></a><br><strong>AI 纪要 · 文字</strong></td>
    <td width="33%"><a href="examples/sections/03-transcript.jpg"><img src="examples/sections/03-transcript.jpg" alt="完整转写"></a><br><strong>完整转写</strong></td>
  </tr>
</table>

## 和 AI 说一句话就行

```text
用 $dingtalk-style-minutes 把这段录音整理成飞书图文纪要。
```

## 安装与运行条件

仓库根目录是项目文档；可安装 Skill 位于 [`skill/dingtalk-style-minutes/`](skill/dingtalk-style-minutes/)。请让 Agent 检查以下依赖，而不是只安装本仓库：

```text
请安装 github.com/PoetCoderJun/dingtalk-style-minutes，
安装 github.com/zarazhangrui/beautiful-feishu-whiteboard，
安装 github.com/larksuite/cli，并确认 lark-doc / lark-shared Skills 可用。
登录飞书，确认目标文档与画板有编辑权限。
若选择 DashScope，再安装 github.com/PoetCoderJun/clean-talking-video，
在隔离 Python 环境安装它的 requirements.txt，并配置 DASHSCOPE_API_KEY。
若选择 FunASR，在隔离环境安装模型与依赖，并将输出规范化为 transcript.json。
```

- Python 3.9–3.13；DashScope 音频代理还需要 FFmpeg / FFprobe。
- Node.js 20+、npm/npx，用于白板检查与渲染；飞书 CLI、已认证用户及可编辑目标。
- `beautiful-feishu-whiteboard` 负责 SVG 与在线画板验证；`lark-doc` 及其共享依赖负责文档操作。安装 CLI 不代表这些 Skills 一定已经可用。
- `requirements-dev.txt` 是测试依赖，不会安装 ASR 模型、clean-talking-video、飞书 CLI 或其 Skills。

## 选择输入路径

| 输入路径 | 实际依赖与边界 |
| --- | --- |
| 现成 `transcript.json` | 跳过 ASR；保留 `segments` 中的 `id`、`start`、`end`、`text`，有可靠分离结果时保留 `speaker_id` |
| DashScope | `transcribe_media.py` 调用 clean-talking-video 的转写器；需要 API key、网络及转写器自身 Python 依赖 |
| 本地 FunASR | 由 Agent 安装模型、运行并转换到上述契约；本仓库没有内置 FunASR 一键适配器，模型首次下载可能需要网络 |

**当前公开版本的兼容性：**clean-talking-video 转写器默认模型为 `qwen3-asr-flash-filetrans`（可由 `DASHSCOPE_ASR_MODEL` 覆盖），但不接受 `--diarization` 或 `--speaker-count`，也不生成 `speaker_id`。本仓库包装入口默认请求说话人分离，因此直接使用默认参数会失败。明确单说话人时使用 `--no-diarization`；多人录音应提供已有可靠分离的转写，或用支持分离的本地模型，不能把单人路径当成多人能力。

以下示例仅适用于明确单说话人，且依赖和 API key 已就绪；运行会调用云服务，可能产生费用：

```bash
python <minutes-skill-root>/scripts/transcribe_media.py \
  --input /data/recording.m4a \
  --output-dir /work/minutes-demo \
  --clean-talking-skill /path/to/clean-talking-video/clean-talking-video \
  --no-diarization
```

`--clean-talking-skill` 或 `CLEAN_TALKING_VIDEO_SKILL` 指向含 `scripts/transcribe.py` 的安装目录，不一定是仓库根目录。不传时入口尝试常见 Codex / Agents Skills 目录。输出为 `transcript.json` 与 `draft.srt`；随后按 [Skill 工作流](skill/dingtalk-style-minutes/SKILL.md)从完整 JSON 建模，而不是只读 SRT。

## 数据会去哪里

DashScope 路径在本地生成压缩音频代理，再上传到 DashScope 临时存储进行识别；不会上传原始视频。FunASR 或已有转写可以跳过云 ASR，但所用 Agent 服务仍可能处理转写文本。

成品流程会把纪要、完整转写与画板写入飞书，并读取在线画板与文档验证结果。因此“本地 FunASR”只说明转写位置，不代表整个流程全本地。若不能上传，请停在本地建模/渲染阶段；该阶段产物不等于已完成的飞书交付。

## 查看证据与验证

上方三张图是[现有输出预览](examples/sections/)，不是可重跑的完整录音案例。项目的公开工程证据包括来源片段关联、转写覆盖检查、SVG 与文档验证器，以及[本地测试夹具](tests/fixtures/)；它们不证明任何客户部署或业务收益。

开发检查只需隔离环境与测试依赖：

```bash
python3 -m venv ../.venv-minutes
../.venv-minutes/bin/python -m pip install -r requirements-dev.txt
../.venv-minutes/bin/python -m unittest discover -s tests -v
```

虚拟环境放在仓库外，避免打包检查将依赖字节码当作发布内容。这组测试无需 API key，不写入飞书；在线画板和最终文档的验证仍属于真实交付步骤。

## 许可

[MIT](LICENSE)。本项目参考钉钉闪记的信息结构，与钉钉或阿里巴巴无关联。
