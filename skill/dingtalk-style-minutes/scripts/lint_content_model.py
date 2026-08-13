#!/usr/bin/env python3
"""Validate adaptive minutes content and transcript provenance."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

BANNED = ("提升效率", "赋能", "底层逻辑", "全面提升", "助力", "闭环赋能")
KINDS = {"cards", "key_points", "timeline", "process", "comparison", "metrics", "quotes", "synthesis"}
CONTENT_TYPES = {"argument", "tutorial", "interview", "meeting", "lecture", "story", "review", "mixed"}
TONES = {"green", "red", "purple", "orange", "teal", "blue"}


def compact(text: str) -> str:
    return re.sub(r"[\s，。；：、,.!?（）()]+", "", str(text))


def visual_len(text: str) -> float:
    return sum(1.0 if ord(ch) > 255 else 0.56 for ch in str(text))


def wrapped_lines(text: str, max_units: float) -> int:
    """Mirror renderer wrapping closely enough to reject overflow, never truncate it."""
    chunks = re.split(r"(?<=[，。；：、,.!?])|\s+", str(text).strip())
    lines, line = 0, ""
    for chunk in filter(None, chunks):
        candidate = line + chunk
        if line and visual_len(candidate) > max_units:
            lines += 1
            line = chunk.lstrip()
        else:
            line = candidate
        while visual_len(line) > max_units:
            cut = max(1, int(max_units))
            while cut > 1 and visual_len(line[:cut]) > max_units:
                cut -= 1
            lines += 1
            line = line[cut:].lstrip()
    return lines + bool(line)


def item_sources(section: dict) -> list[str]:
    if section["kind"] == "synthesis":
        return section.get("source_segment_ids", [])
    return [sid for item in section.get("items", []) for sid in item.get("source_segment_ids", [])]


def unit_texts(section: dict) -> list[list[str]]:
    if section["kind"] == "synthesis":
        return [[section.get("text", "")]]
    units=[]
    for item in section.get("items", []):
        units.append([str(item.get(key,"")) for key in ("title","label","value","note","quote","takeaway") if item.get(key)] + [str(x) for x in item.get("bullets",[])])
    return units


def phrase_matches(phrase: str, prose_parts: list[str]) -> bool:
    phrase=compact(phrase)
    if len(phrase)<4: return False
    for part in prose_parts:
        candidate=compact(part)
        if phrase in candidate or difflib.SequenceMatcher(None,phrase,candidate).ratio()>=0.78: return True
        # Short card claims may be expanded with modal words while retaining most of their substance.
        match=difflib.SequenceMatcher(None,phrase,candidate).find_longest_match(0,len(phrase),0,len(candidate))
        if match.size>=4 and match.size/max(1,len(phrase))>=0.55: return True
    return False


def independent_evidence_matches(prose_sources: set[str], board_units: list[set[str]]) -> int:
    """Maximum one-to-one matches: one repeated segment cannot impersonate many units."""
    unit_to_source:dict[int,str]={}
    def augment(source: str, seen: set[int]) -> bool:
        for index,unit in enumerate(board_units):
            if source not in unit or index in seen: continue
            seen.add(index)
            if index not in unit_to_source or augment(unit_to_source[index],seen):
                unit_to_source[index]=source
                return True
        return False
    for source in sorted(prose_sources): augment(source,set())
    return len(unit_to_source)


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("model",type=Path); parser.add_argument("--transcript",type=Path); args=parser.parse_args()
    model=json.loads(args.model.read_text(encoding="utf-8")); failures=[]
    transcript_path=args.transcript or Path(model.get("source",{}).get("transcript_path", ""))
    transcript=None
    if not str(transcript_path):
        failures.append("transcript path is required for provenance validation")
    elif not transcript_path.is_file():
        failures.append(f"transcript not found: {transcript_path}")
    else:
        transcript=json.loads(transcript_path.read_text(encoding="utf-8"))
        if not isinstance(transcript.get("segments"),list) or not transcript.get("segments"):
            failures.append("transcript must contain at least one segment")
    segment_ids={seg["id"] for seg in transcript.get("segments",[])} if transcript else set()
    if transcript and transcript.get("diarization_enabled"):
        speakers=transcript.get("speakers",{})
        if not speakers: failures.append("diarized transcript requires a speakers map")
        for segment in transcript.get("segments",[]):
            if segment.get("speaker_id") is None: failures.append(f"diarized transcript segment lacks speaker_id: {segment.get('id')}")
            elif str(segment["speaker_id"]) not in speakers: failures.append(f"unknown speaker_id at {segment.get('id')}")
    if model.get("schema_version") != 3: failures.append("schema_version must be 3")
    overview=model.get("overview","").strip()
    if not 30 <= len(compact(overview)) <= 240: failures.append("overview must be one concise 30-240 character paragraph")
    if "\n" in overview: failures.append("overview must not contain headings, lists, or line breaks")
    minutes=model.get("minutes",{}); sections=minutes.get("sections",[])
    if minutes.get("content_type") not in CONTENT_TYPES: failures.append("invalid minutes.content_type")
    if wrapped_lines(minutes.get("title",""), 31) > 1: failures.append("minutes title exceeds one visual line")
    if wrapped_lines(minutes.get("subtitle",""), 69) > 2: failures.append("minutes subtitle exceeds two visual lines")
    if not 3 <= len(sections) <= 7: failures.append("board needs 3-7 content-driven sections")
    ids=[]
    for section in sections:
        sid=section.get("id",""); ids.append(sid); kind=section.get("kind")
        if not sid or not section.get("title"): failures.append("every section requires id and title")
        if section.get("tone") and section.get("tone") not in TONES: failures.append(f"{sid}: unsupported tone {section.get('tone')}")
        if wrapped_lines(section.get("title",""), 44) > 1: failures.append(f"{sid}: section title exceeds one visual line")
        if wrapped_lines(section.get("intro",""), 76) > 2: failures.append(f"{sid}: intro exceeds two visual lines")
        if kind not in KINDS: failures.append(f"{sid}: unsupported kind {kind}"); continue
        sources=item_sources(section)
        if not sources: failures.append(f"{sid}: no ASR provenance")
        if segment_ids and set(sources)-segment_ids: failures.append(f"{sid}: unknown source segments {sorted(set(sources)-segment_ids)}")
        if kind in {"cards","key_points","comparison"}:
            items=section.get("items",[])
            if not 2 <= len(items) <= 6: failures.append(f"{sid}: {kind} requires 2-6 items")
            if kind=="comparison" and len(items)!=2: failures.append(f"{sid}: comparison requires exactly two genuine sides")
            cols=4 if len(items)==4 else min(3,max(1,len(items)))
            units=39 if kind=="comparison" else (18 if cols==4 else 26 if cols==3 else 40)
            for item in items:
                if not item.get("id"): failures.append(f"{sid}: every card item requires id")
                if not item.get("title"): failures.append(f"{sid}/{item.get('id')}: every card item requires title")
                if not item.get("source_segment_ids"): failures.append(f"{sid}/{item.get('id')}: every card item requires source_segment_ids")
                bullets=item.get("bullets",[])
                emphasis=item.get("emphasis",[])
                if not 2 <= len(bullets) <= 5: failures.append(f"{sid}/{item.get('id')}: requires 2-5 bullets")
                if not 1 <= len(emphasis) <= 4: failures.append(f"{sid}/{item.get('id')}: requires 1-4 semantic emphasis phrases")
                for phrase in emphasis:
                    if sum(str(bullet).count(str(phrase)) for bullet in bullets)!=1: failures.append(f"{sid}/{item.get('id')}: emphasis must occur exactly once in bullets: {phrase}")
                if len({compact(x) for x in bullets}) != len(bullets): failures.append(f"{sid}/{item.get('id')}: duplicate bullets")
                if wrapped_lines(item.get("title",""), units-4) > 2: failures.append(f"{sid}/{item.get('id')}: item title exceeds two visual lines")
                if wrapped_lines(item.get("takeaway",""), units+2) > 2: failures.append(f"{sid}/{item.get('id')}: takeaway exceeds two visual lines")
                if sum(wrapped_lines(b,units) for b in bullets)>8: failures.append(f"{sid}/{item.get('id')}: card body exceeds eight visual lines")
        elif kind in {"timeline","process"}:
            if not 2 <= len(section.get("items",[])) <= 8: failures.append(f"{sid}: process requires 2-8 steps")
            for item in section.get("items",[]):
                if not item.get("title"): failures.append(f"{sid}: every process item requires title")
                if not 1 <= len(item.get("bullets",[])) <= 5: failures.append(f"{sid}/{item.get('title')}: process item requires 1-5 bullets")
                if not item.get("source_segment_ids"): failures.append(f"{sid}/{item.get('title')}: every process item requires source_segment_ids")
                emphasis=item.get("emphasis",[])
                if not 1 <= len(emphasis) <= 4: failures.append(f"{sid}/{item.get('title')}: requires 1-4 semantic emphasis phrases")
                for phrase in emphasis:
                    if sum(str(bullet).count(str(phrase)) for bullet in item.get("bullets",[]))!=1: failures.append(f"{sid}/{item.get('title')}: emphasis must occur exactly once in bullets: {phrase}")
                if wrapped_lines(item.get("title",""),19)>1: failures.append(f"{sid}/{item.get('title')}: step title exceeds one visual line")
                if sum(wrapped_lines(b,19) for b in item.get("bullets",[]))>5: failures.append(f"{sid}/{item.get('title')}: step body exceeds five visual lines")
                if wrapped_lines(item.get("takeaway",""),20)>1: failures.append(f"{sid}/{item.get('title')}: step takeaway exceeds one visual line")
        elif kind=="metrics":
            if not 2 <= len(section.get("items",[])) <= 8: failures.append(f"{sid}: metrics requires 2-8 items")
            for item in section.get("items",[]):
                if not item.get("source_segment_ids"): failures.append(f"{sid}/{item.get('label')}: every metric requires source_segment_ids")
                if wrapped_lines(item.get("label",""),20)>1: failures.append(f"{sid}/{item.get('label')}: metric label exceeds one visual line")
                if wrapped_lines(item.get("value",""),20)>2: failures.append(f"{sid}/{item.get('label')}: metric value exceeds two visual lines")
                if wrapped_lines(item.get("note",""), 22)>3: failures.append(f"{sid}/{item.get('label')}: metric note exceeds three visual lines")
        elif kind=="quotes":
            if not 1 <= len(section.get("items",[])) <= 5: failures.append(f"{sid}: quotes requires 1-5 items")
            for item in section.get("items",[]):
                if not item.get("source_segment_ids"): failures.append(f"{sid}: every quote requires source_segment_ids")
                if wrapped_lines(item.get("quote",""),62)>8: failures.append(f"{sid}: quote exceeds eight visual lines")
        elif kind=="synthesis":
            if not section.get("text"): failures.append(f"{sid}: synthesis text required")
            if wrapped_lines(section.get("text",""),76)>4: failures.append(f"{sid}: synthesis exceeds four visual lines")
        text=json.dumps(section,ensure_ascii=False)
        for term in BANNED:
            if term in text: failures.append(f"{sid}: generic phrase {term}")
    if len(ids)!=len(set(ids)): failures.append("section ids must be unique")
    prose_sections=minutes.get("prose_sections",[])
    if not 2 <= len(prose_sections) <= 7: failures.append("AI minutes require 2-7 independent hierarchical prose_sections")
    prose_sources=[]
    board_titles={item.get("title") for section in sections for item in section.get("items",[])}
    for section in prose_sections:
        if not section.get("title"): failures.append("every prose section needs a title")
        if section.get("title") in board_titles: failures.append(f"prose heading copies a board-card title: {section.get('title')}")
        if "paragraphs" in section: failures.append(f"{section.get('title')}: essay paragraphs are not allowed; use claim/detail hierarchy")
        points=section.get("points",[])
        if not 2 <= len(points) <= 4: failures.append(f"{section.get('title')}: requires 2-4 scan-first points")
        claims=[]; sources=[]
        for point in points:
            claim=str(point.get("claim","")).strip(); claims.append(compact(claim))
            if not 6 <= len(compact(claim)) <= 42: failures.append(f"{section.get('title')}: claim must be a concise 6-42 character conclusion")
            if "\n" in claim: failures.append(f"{section.get('title')}: claim must fit one line")
            details=point.get("details",[])
            if not 1 <= len(details) <= 3: failures.append(f"{section.get('title')}/{claim}: requires 1-3 evidence details")
            if any(not 12 <= len(compact(detail)) <= 140 for detail in details): failures.append(f"{section.get('title')}/{claim}: detail must be a developed 12-140 character fact, mechanism, or implication")
            point_sources=point.get("source_segment_ids",[]); sources.extend(point_sources)
            if not point_sources: failures.append(f"{section.get('title')}/{claim}: point has no ASR provenance")
            if segment_ids and set(point_sources)-segment_ids: failures.append(f"{section.get('title')}/{claim}: point cites unknown segments")
        if len(claims)!=len(set(claims)): failures.append(f"{section.get('title')}: point claims must be unique")
        prose_sources.extend(sources)
        for term in BANNED:
            if term in json.dumps(section,ensure_ascii=False): failures.append(f"{section.get('title')}: generic phrase {term}")
    board_sources={sid for section in sections for sid in item_sources(section)}
    if board_sources and not board_sources.intersection(prose_sources): failures.append("board and prose do not share any evidence spine")
    # Prose must synthesize across visual units; one prose section mirroring one item is a rejected card expansion.
    board_item_sources=[]; board_unit_text=[]
    for section in sections:
        if section["kind"]=="synthesis": board_item_sources.append(set(section.get("source_segment_ids",[])))
        else: board_item_sources.extend(set(item.get("source_segment_ids",[])) for item in section.get("items",[]))
        board_unit_text.extend(unit_texts(section))
    for prose in prose_sections:
        ps={sid for point in prose.get("points",[]) for sid in point.get("source_segment_ids",[])}
        if len(ps)<2: failures.append(f"{prose.get('title')}: prose needs at least two distinct source segments")
        if len(board_item_sources)>1 and independent_evidence_matches(ps,board_item_sources)<2:
            failures.append(f"{prose.get('title')}: prose must synthesize evidence from at least two visual units")
        prose_parts=[prose.get("title","")]+[part for point in prose.get("points",[]) for part in [point.get("claim","")]+point.get("details",[])]+([prose["callout"]] if prose.get("callout") else [])
        mirrored_units=0
        for phrases in board_unit_text:
            meaningful=[p for p in phrases if len(compact(p))>=4]
            if len(meaningful)>=2 and sum(phrase_matches(p,prose_parts) for p in meaningful)>=max(2,(len(meaningful)+1)//2): mirrored_units+=1
        # Three visual units being substantially restated is card-by-card expansion; two may be legitimate contrast.
        if mirrored_units>=3: failures.append(f"{prose.get('title')}: prose point-by-point mirrors multiple visual units")
    chapters=model.get("chapters",[])
    if not chapters: failures.append("chaptered transcript is required")
    covered=[]; last_end=-1.0; source_order=[seg["id"] for seg in transcript.get("segments",[])] if transcript else []
    for chapter in chapters:
        if not chapter.get("title") or not chapter.get("summary"): failures.append("each chapter needs title and summary")
        start,end=float(chapter.get("start",-1)),float(chapter.get("end",-1))
        if start<last_end-0.05 or end<=start: failures.append(f"chapter order/range invalid: {chapter.get('title')}")
        last_end=end; chapter_ids=chapter.get("segment_ids",[]); covered.extend(chapter_ids)
        if segment_ids and set(chapter_ids)-segment_ids: failures.append(f"chapter {chapter.get('title')}: unknown segment ids")
        if transcript and chapter_ids:
            positions=[source_order.index(sid) for sid in chapter_ids]
            if positions != list(range(positions[0],positions[0]+len(positions))): failures.append(f"chapter {chapter.get('title')}: segments are not contiguous and ordered")
            first,last=(next(seg for seg in transcript["segments"] if seg["id"]==chapter_ids[0]),next(seg for seg in transcript["segments"] if seg["id"]==chapter_ids[-1]))
            if abs(start-float(first["start"]))>0.051 or abs(end-float(last["end"]))>0.051: failures.append(f"chapter {chapter.get('title')}: start/end do not match first/last segment")
    if segment_ids and set(covered)!=segment_ids: failures.append(f"chapters must cover every transcript segment exactly once; missing={len(segment_ids-set(covered))}")
    if len(covered)!=len(set(covered)): failures.append("a transcript segment appears in multiple chapters")
    if transcript and covered!=source_order: failures.append("chapter segment_ids must equal the source transcript order exactly")
    if failures:
        print("FAIL"); print("\n".join(f"- {x}" for x in failures)); return 1
    print(f"PASS: {len(sections)} adaptive sections, {len(chapters)} chapters, provenance intact"); return 0


if __name__=="__main__": sys.exit(main())
