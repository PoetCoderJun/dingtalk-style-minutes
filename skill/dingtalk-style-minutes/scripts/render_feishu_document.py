#!/usr/bin/env python3
"""Render the invariant three-part Feishu document body from schema v3."""

from __future__ import annotations

import argparse,html,json
from pathlib import Path

def ts(value: float)->str:
    seconds=max(0,int(round(float(value)))); h,rem=divmod(seconds,3600); m,s=divmod(rem,60); return f"{h:02d}:{m:02d}:{s:02d}"

def speaker_label(transcript: dict, segment: dict)->str:
    speaker_id=segment.get("speaker_id")
    if speaker_id is None: return ""
    speaker=transcript.get("speakers",{}).get(str(speaker_id),{})
    return str(speaker.get("name") or speaker.get("label") or f"发言人 {speaker_id}").strip()

def main()->None:
    p=argparse.ArgumentParser(); p.add_argument("--model",type=Path,required=True); p.add_argument("--transcript",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--whiteboard-token",required=True); a=p.parse_args()
    if not a.whiteboard_token.strip() or a.whiteboard_token.upper() in {"TOKEN","WHITEBOARD_TOKEN","PLACEHOLDER"}:
        p.error("--whiteboard-token must be a real Feishu whiteboard token")
    model=json.loads(a.model.read_text(encoding="utf-8")); transcript=json.loads(a.transcript.read_text(encoding="utf-8")); by_id={s["id"]:s for s in transcript["segments"]}; minutes=model["minutes"]
    out=["<h1>一、内容概览</h1>",f"<p>{html.escape(model['overview'])}</p>","<h1>二、AI 纪要</h1>",f'<whiteboard token="{html.escape(a.whiteboard_token)}"></whiteboard>']
    for section in minutes["prose_sections"]:
        out.append(f"<h2>{html.escape(section['title'])}</h2>")
        points=[]
        for point in section["points"]:
            details="".join(f"<li>{html.escape(detail)}</li>" for detail in point["details"])
            points.append(f"<li><b>{html.escape(point['claim'])}</b><ul>{details}</ul></li>")
        out.append("<ul>"+"".join(points)+"</ul>")
        if section.get("callout"):
            out.append(f'<callout emoji="📌" background-color="light-yellow" border-color="yellow"><p>{html.escape(section["callout"])}</p></callout>')
    out += ["<h1>三、完整转写</h1>","<h2>概述</h2>",f"<p>{html.escape(minutes['subtitle'])}</p>"]
    for chapter in model["chapters"]:
        out.append(f'<h2>【{ts(chapter["start"])}–{ts(chapter["end"])}】{html.escape(chapter["title"])}</h2>'); out.append(f"<p>{html.escape(chapter['summary'])}</p>")
        for sid in chapter["segment_ids"]:
            seg=by_id[sid]; label=speaker_label(transcript,seg); prefix=f'<b>{html.escape(label)}</b>：' if label else ""; out.append(f'<p><span text-color="gray">[{ts(seg["start"])}]</span> {prefix}{html.escape(seg["text"])}</p>')
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text("\n".join(out)+"\n",encoding="utf-8"); print(a.output.resolve())

if __name__=="__main__": main()
