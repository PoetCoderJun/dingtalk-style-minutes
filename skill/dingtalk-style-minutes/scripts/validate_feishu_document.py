#!/usr/bin/env python3
"""Validate the invariant three-part Feishu XML document contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def node_text(node: ET.Element) -> str:
    return "".join(node.itertext()).strip()


def ts(value: float) -> str:
    seconds=max(0,int(round(float(value)))); h,rem=divmod(seconds,3600); m,s=divmod(rem,60); return f"{h:02d}:{m:02d}:{s:02d}"

def speaker_label(transcript: dict, segment: dict) -> str:
    speaker_id=segment.get("speaker_id")
    if speaker_id is None: return ""
    speaker=transcript.get("speakers",{}).get(str(speaker_id),{})
    return str(speaker.get("name") or speaker.get("label") or f"发言人 {speaker_id}").strip()


def validate_minutes_list(node: ET.Element, section: dict, failures: list[str]) -> None:
    outer=node.findall("./li")
    if len(outer)!=len(section["points"]):
        failures.append(f"AI minutes point count mismatch: {section['title']}")
        return
    for li,point in zip(outer,section["points"]):
        bold=li.find("./b")
        if bold is None or node_text(bold)!=point["claim"]:
            failures.append(f"AI minutes claim mismatch: {section['title']} / {point['claim']}")
        nested=li.find("./ul")
        details=[] if nested is None else [node_text(item) for item in nested.findall("./li")]
        if details!=point["details"]:
            failures.append(f"AI minutes details mismatch: {section['title']} / {point['claim']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("document", type=Path)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--whiteboard-token")
    args = parser.parse_args()
    model = json.loads(args.model.read_text(encoding="utf-8"))
    transcript = json.loads(args.transcript.read_text(encoding="utf-8"))
    root = ET.fromstring("<root>" + args.document.read_text(encoding="utf-8") + "</root>")
    failures: list[str] = []
    h1s = [node.text or "" for node in root.findall("h1")]
    required = ["一、内容概览", "二、AI 纪要", "三、完整转写"]
    if h1s != required:
        failures.append(f"top-level headings {h1s} != {required}")
    children = list(root)
    try:
        first = next(i for i,n in enumerate(children) if n.tag == "h1" and n.text == required[0])
        second = next(i for i,n in enumerate(children) if n.tag == "h1" and n.text == required[1])
        third = next(i for i,n in enumerate(children) if n.tag == "h1" and n.text == required[2])
    except StopIteration:
        first = second = third = 0
    if not (first < second < third):
        failures.append("top-level sections are not ordered")
    overview_nodes = children[first+1:second]
    if len(overview_nodes) != 1 or overview_nodes[0].tag != "p":
        failures.append("content overview must contain exactly one paragraph")
    elif node_text(overview_nodes[0]) != model["overview"].strip():
        failures.append("content overview does not match model")
    ai_nodes = children[second+1:third]
    if len([n for n in ai_nodes if n.tag == "whiteboard"]) != 1:
        failures.append("AI minutes must contain exactly one whiteboard")
    if not ai_nodes or ai_nodes[0].tag != "whiteboard":
        failures.append("whiteboard must be the first block under AI minutes")
    if ai_nodes and ai_nodes[0].tag == "whiteboard":
        token=(ai_nodes[0].attrib.get("token") or "").strip()
        if not token or token.upper() in {"TOKEN","WHITEBOARD_TOKEN","PLACEHOLDER"}:
            failures.append("whiteboard token is empty or a placeholder")
        if args.whiteboard_token and token != args.whiteboard_token:
            failures.append("whiteboard token does not match the expected token")
    if any(node.tag == "h3" for node in ai_nodes):
        failures.append("AI prose must not expand board cards as h3 blocks")
    prose_headings=[n.text or "" for n in ai_nodes if n.tag=="h2"]
    if prose_headings != [s["title"] for s in model["minutes"]["prose_sections"]]: failures.append("AI prose headings do not match model")
    if any(n.tag=="p" for n in ai_nodes): failures.append("AI minutes must not contain top-level essay paragraphs")
    prose_lists=[n for n in ai_nodes if n.tag=="ul"]
    if len(prose_lists)!=len(model["minutes"]["prose_sections"]): failures.append("AI minutes must contain one hierarchical list per topic")
    for node,section in zip(prose_lists,model["minutes"]["prose_sections"]): validate_minutes_list(node,section,failures)
    transcript_nodes = children[third+1:]
    if not transcript_nodes or transcript_nodes[0].tag != "h2" or transcript_nodes[0].text != "概述":
        failures.append("full transcript must begin with 概述")
    if len(transcript_nodes)<2 or transcript_nodes[1].tag!="p" or (transcript_nodes[1].text or "").strip()!=model["minutes"]["subtitle"].strip(): failures.append("full transcript overview does not match model")
    chapter_headings = [n for n in transcript_nodes if n.tag == "h2" and (n.text or "").startswith("【")]
    if len(chapter_headings) != len(model["chapters"]):
        failures.append(f"chapter heading count {len(chapter_headings)} != {len(model['chapters'])}")
    timestamp_pattern = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]$")
    timestamp_paragraphs = []
    for node in transcript_nodes:
        if node.tag == "p" and len(node) and node[0].tag == "span" and timestamp_pattern.match(node[0].text or ""):
            timestamp_paragraphs.append(node)
    if len(timestamp_paragraphs) != len(transcript["segments"]):
        failures.append(f"timestamped transcript paragraphs {len(timestamp_paragraphs)} != source segments {len(transcript['segments'])}")
    rendered_times = [node[0].text for node in timestamp_paragraphs]
    if rendered_times != sorted(rendered_times):
        failures.append("timestamped transcript is not chronological")
    for node,segment in zip(timestamp_paragraphs,transcript["segments"]):
        label=speaker_label(transcript,segment)
        if label:
            bold=node.find("./b")
            if bold is None or node_text(bold)!=label: failures.append(f"speaker label mismatch at {segment['id']}")
            rendered_text=(bold.tail or "").strip().removeprefix("：").strip() if bold is not None else ""
        else:
            rendered_text=(node[0].tail or "").strip()
        if rendered_text != str(segment["text"]).strip(): failures.append(f"transcript text mismatch at {segment['id']}")
        seconds=max(0,int(round(float(segment['start'])))); h,rem=divmod(seconds,3600); m,s=divmod(rem,60); expected_time=f"[{h:02d}:{m:02d}:{s:02d}]"
        if node[0].text != expected_time: failures.append(f"transcript timestamp mismatch at {segment['id']}")
    expected_chapter_titles=[]
    for chapter in model["chapters"]:
        expected_chapter_titles.append(f"【{ts(chapter['start'])}–{ts(chapter['end'])}】{chapter['title']}")
    if [n.text for n in chapter_headings] != expected_chapter_titles: failures.append("chapter titles or time ranges do not match model")
    for heading,chapter in zip(chapter_headings,model["chapters"]):
        index=transcript_nodes.index(heading)
        if index+1>=len(transcript_nodes) or transcript_nodes[index+1].tag!="p" or (transcript_nodes[index+1].text or "").strip()!=chapter["summary"].strip(): failures.append(f"chapter summary mismatch: {chapter['title']}")
    # Exact top-level grammar rejects extra navigation blocks and binds every segment to its chapter.
    expected_blocks=[("h1","一、内容概览"),("p",model["overview"]),("h1","二、AI 纪要"),("whiteboard","")]
    for prose in model["minutes"]["prose_sections"]:
        expected_blocks.append(("h2",prose["title"]))
        expected_blocks.append(("ul","".join(point["claim"]+"".join(point["details"]) for point in prose["points"])))
        if prose.get("callout"): expected_blocks.append(("callout",prose["callout"]))
    expected_blocks += [("h1","三、完整转写"),("h2","概述"),("p",model["minutes"]["subtitle"])]
    segments_by_id={seg["id"]:seg for seg in transcript["segments"]}
    for chapter in model["chapters"]:
        expected_blocks += [("h2",f"【{ts(chapter['start'])}–{ts(chapter['end'])}】{chapter['title']}"),("p",chapter["summary"])]
        for segment_id in chapter["segment_ids"]:
            segment=segments_by_id[segment_id]
            label=speaker_label(transcript,segment)
            speaker_prefix=f"{label}：" if label else ""
            expected_blocks.append(("p",f"[{ts(segment['start'])}] {speaker_prefix}{str(segment['text']).strip()}"))
    actual_blocks=[(node.tag,"" if node.tag=="whiteboard" else node_text(node)) for node in children]
    if actual_blocks!=expected_blocks:
        mismatch=next((i for i,(actual,expected) in enumerate(zip(actual_blocks,expected_blocks)) if actual!=expected),min(len(actual_blocks),len(expected_blocks)))
        failures.append(f"document block grammar/ownership mismatch at index {mismatch}: actual={actual_blocks[mismatch:mismatch+1]} expected={expected_blocks[mismatch:mismatch+1]}")
    if failures:
        print("FAIL")
        print("\n".join(f"- {item}" for item in failures))
        return 1
    print(f"PASS: exact three-part document, {len(chapter_headings)} chapters, {len(timestamp_paragraphs)} transcript segments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
