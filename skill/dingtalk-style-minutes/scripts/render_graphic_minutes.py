#!/usr/bin/env python3
"""Render an adaptive portrait graphic-minutes SVG from schema v3."""

from __future__ import annotations

import argparse
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

W = 1680
INK, MUTED, RULE, WHITE = "#26282B", "#71777F", "#DFE3E6", "#FFFFFF"
TONES = {
    "green": {"accent": "#20A35A", "tint": "#EFFAF4", "line": "#BFEAD0", "strip": "#E6F7EE"},
    "red": {"accent": "#C95C5C", "tint": "#FFF4F4", "line": "#F1CFCF", "strip": "#FCEDED"},
    "purple": {"accent": "#7055D8", "tint": "#F6F3FF", "line": "#D9D0F8", "strip": "#EFEAFF"},
    "orange": {"accent": "#D88818", "tint": "#FFF8ED", "line": "#F1D6A8", "strip": "#FCF0DE"},
    "teal": {"accent": "#169B9B", "tint": "#EFFAFA", "line": "#BDE6E5", "strip": "#E2F6F5"},
    "blue": {"accent": "#3C78D8", "tint": "#F1F6FE", "line": "#C9D9F5", "strip": "#E8F0FD"},
}
TONE_ORDER = ["green", "red", "purple", "orange", "teal", "blue"]


def esc(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def visual_len(text: str) -> float:
    return sum(1.0 if ord(ch) > 255 else 0.56 for ch in str(text))


def wrap(text: str, max_units: float) -> list[str]:
    text = str(text).strip()
    if not text:
        return [""]
    chunks = re.split(r"(?<=[，。；：、,.!?])|\s+", text)
    lines, line = [], ""
    for chunk in filter(None, chunks):
        candidate = line + chunk
        if line and visual_len(candidate) > max_units:
            lines.append(line.rstrip()); line = chunk.lstrip()
        else:
            line = candidate
        while visual_len(line) > max_units:
            cut = max(1, int(max_units))
            while cut > 1 and visual_len(line[:cut]) > max_units:
                cut -= 1
            lines.append(line[:cut].rstrip()); line = line[cut:].lstrip()
    if line:
        lines.append(line.rstrip())
    return lines or [text]


def wrap_for_emphasis(text: str, max_units: float, emphasis: list[str]) -> list[str]:
    """Wrap without splitting a semantic emphasis phrase across visual lines."""
    protected=str(text)
    placeholders={}
    for index,phrase in enumerate(sorted(emphasis,key=len,reverse=True)):
        token=chr(0xE000+index)
        if phrase in protected:
            protected=protected.replace(phrase,token,1); placeholders[token]=phrase
    chunks=re.split(r"(?<=[，。；：、,.!?])|\s+",protected.strip()); lines=[]; line=""
    def units(value: str)->float:
        return visual_len("".join(placeholders.get(ch,ch) for ch in value))
    for chunk in filter(None,chunks):
        candidate=line+chunk
        if line and units(candidate)>max_units: lines.append(line.rstrip()); line=chunk.lstrip()
        else: line=candidate
        while units(line)>max_units:
            cut=1
            while cut<len(line) and units(line[:cut+1])<=max_units: cut+=1
            if cut==1 and line[0] in placeholders: cut=1
            lines.append(line[:cut].rstrip()); line=line[cut:].lstrip()
    if line: lines.append(line.rstrip())
    return ["".join(placeholders.get(ch,ch) for ch in line) for line in lines] or [str(text)]


class SVG:
    def __init__(self, height: int) -> None:
        self.height = height
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" height="{height}" data-role="report-page">']

    def add(self, raw: str) -> None: self.parts.append(raw)
    def rect(self, x, y, w, h, fill, *, stroke="none", sw=0, rx=0, role="", extra=""):
        attr = f' data-role="{role}"' if role else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{attr}{extra}/>')
    def line(self, x1, y1, x2, y2, stroke, sw=2): self.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}"/>')
    def circle(self, cx, cy, r, fill): self.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>')
    def text(self, x, y, text, size, *, weight=400, fill=INK, role="", anchor="start", extra=""):
        attr = f' data-role="{role}"' if role else ""
        self.add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{attr}{extra}>{esc(text)}</text>')
    def multiline(self, x, y, lines, size, *, line_h, weight=400, fill=INK, role="", bullet=False):
        attr = f' data-role="{role}"' if role else ""
        self.add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}"{attr}>')
        for index, line in enumerate(lines):
            prefix = "•  " if bullet and index == 0 else ("   " if bullet else "")
            self.add(f'<tspan x="{x}" dy="{0 if index == 0 else line_h}">{esc(prefix + line)}</tspan>')
        self.add("</text>")
    def finish(self) -> str: return "\n".join(self.parts + ["</svg>"])


def emphasized_lines(svg: SVG, x: int, y: int, text: str, emphasis: list[str], tone: dict, units: int, *, size: int=17, line_h: int=24, bullet: bool=True) -> int:
    """Render one wrapped bullet while preserving bold accent spans as editable text."""
    lines=wrap_for_emphasis(text,units,emphasis); used=set(); char_units=size
    for line_index,line in enumerate(lines):
        cursor_x=x
        if bullet:
            prefix="•  " if line_index==0 else "   "
            svg.text(cursor_x,y+line_index*line_h,prefix,size,role="body")
            cursor_x+=visual_len(prefix)*char_units
        parts=[]; position=0
        matches=[]
        for phrase in emphasis:
            start=line.find(phrase)
            if start>=0 and phrase not in used: matches.append((start,phrase))
        for start,phrase in sorted(matches):
            if start<position: continue
            if start>position: parts.append((line[position:start],False))
            parts.append((phrase,True)); position=start+len(phrase); used.add(phrase)
        if position<len(line): parts.append((line[position:],False))
        if not parts: parts=[(line,False)]
        for part,is_emphasis in parts:
            svg.text(cursor_x,y+line_index*line_h,part,size,weight=700 if is_emphasis else 400,fill=tone["accent"] if is_emphasis else INK,role="body-emphasis" if is_emphasis else "body")
            cursor_x+=visual_len(part)*char_units
    return len(lines)


def group_open(svg: SVG, role: str, **attrs: str) -> None:
    extra = " ".join(f'data-{key.replace("_", "-")}="{esc(value)}"' for key, value in attrs.items())
    svg.add(f'<g data-role="{role}" {extra}>')


def draw_icon(svg: SVG, x: int, y: int, icon: str, tone: dict) -> None:
    svg.rect(x, y, 26, 26, tone["tint"], stroke=tone["accent"], sw=1, rx=6)
    c, cx = tone["accent"], x + 13
    if icon in {"history", "↻"}:
        svg.add(f'<path d="M {x+7} {y+12} A 7 7 0 1 0 {x+11} {y+6}" fill="none" stroke="{c}" stroke-width="2"/>')
    elif icon in {"shield", "◒"}:
        svg.add(f'<path d="M {cx} {y+5} L {x+20} {y+8} L {x+19} {y+17} L {cx} {y+22} L {x+7} {y+17} L {x+6} {y+8} Z" fill="none" stroke="{c}" stroke-width="2"/>')
    elif icon in {"search", "⌕"}:
        svg.add(f'<circle cx="{x+11}" cy="{y+11}" r="5" fill="none" stroke="{c}" stroke-width="2"/>'); svg.line(x+15,y+15,x+21,y+21,c,2)
    elif icon in {"branch", "⌘"}:
        svg.line(cx,y+5,cx,y+21,c,2); svg.line(x+6,y+8,x+20,y+18,c,2); svg.circle(cx,y+5,2,c); svg.circle(x+6,y+8,2,c); svg.circle(x+20,y+18,2,c)
    elif icon in {"team", "●"}:
        svg.circle(cx,y+9,4,c); svg.circle(x+7,y+12,3,c); svg.circle(x+19,y+12,3,c); svg.add(f'<path d="M {x+6} {y+21} Q {cx} {y+14} {x+20} {y+21}" fill="none" stroke="{c}" stroke-width="2"/>')
    else:
        svg.line(x+7,y+8,x+19,y+8,c,2); svg.line(x+7,y+13,x+17,y+13,c,2); svg.line(x+7,y+18,x+15,y+18,c,2)


def tone_for(section: dict, index: int) -> tuple[str, dict]:
    name = section.get("tone") or TONE_ORDER[index % len(TONE_ORDER)]
    return name, TONES[name]


def item_lines(item: dict, units: int) -> int:
    return sum(len(wrap(bullet, units)) for bullet in item.get("bullets", []))


def card_required_height(item: dict, units: int) -> int:
    """Size a card from its visible text instead of a presentation-like fixed floor."""
    title_lines = max(1, len(wrap(item.get("title", ""), max(8, units - 4))))
    body_top = max(82, 20 + title_lines * 26 + 24)
    bullets = item.get("bullets", [])
    body_height = sum(len(wrap(bullet, units)) * 24 + 6 for bullet in bullets)
    takeaway_lines = len(wrap(item.get("takeaway", ""), units + 2)) if item.get("takeaway") else 0
    takeaway_height = max(46, takeaway_lines * 18 + 16) if takeaway_lines else 0
    bottom = 14 + takeaway_height + 18 if takeaway_lines else 22
    return max(196, body_top + body_height + bottom)


def card_row_heights(items: list[dict], cols: int, units: int) -> list[int]:
    return [
        max(card_required_height(item, units) for item in items[start : start + cols])
        for start in range(0, len(items), cols)
    ]


def timeline_item_required_height(item: dict, units: int) -> int:
    title_lines = max(1, len(wrap(item.get("title", ""), units)))
    cursor = 94 + title_lines * 25 + 13
    body_height = sum(len(wrap(bullet, units)) * 23 + 8 for bullet in item.get("bullets", []))
    takeaway_lines = len(wrap(item.get("takeaway", ""), units)) if item.get("takeaway") else 0
    takeaway_height = max(40, takeaway_lines * 18 + 16) if takeaway_lines else 0
    bottom = 18 + takeaway_height + 18 if takeaway_lines else 22
    return cursor + body_height + bottom


def process_rows(items: list) -> list[list]:
    """Balance multi-row processes so the last row does not look abandoned."""
    count = len(items)
    if count <= 4:
        return [items]
    columns = 4 if count in {7, 8} else 3
    return [items[start:start + columns] for start in range(0, count, columns)]


def metric_required_height(item: dict, units: int) -> int:
    label_lines = max(1, len(wrap(item.get("label", ""), units)))
    value_lines = max(1, len(wrap(item.get("value", ""), units)))
    note_lines = len(wrap(item.get("note", ""), units + 2)) if item.get("note") else 0
    value_y = 36 + label_lines * 21 + 12
    note_y = value_y + value_lines * 26 + 10
    return note_y + note_lines * 20 + 18 if note_lines else value_y + value_lines * 26 + 20


def quote_required_height(item: dict) -> int:
    return max(82, 52 + 25 * len(wrap(item.get("quote", ""), 62)))


def synthesis_required_height(section: dict) -> int:
    return max(76, 36 + 28 * len(wrap(section.get("text", ""), 76)))


def section_height(section: dict) -> int:
    kind, items = section["kind"], section.get("items", [])
    intro = 54 if section.get("intro") else 0
    if kind in {"cards", "key_points"}:
        cols = 4 if len(items) == 4 else min(3, max(1, len(items)))
        rows = math.ceil(len(items) / cols)
        units = 18 if cols == 4 else 26 if cols == 3 else 40
        row_heights = card_row_heights(items, cols, units)
        panel_height = 46 + sum(row_heights) + (rows - 1) * 20
        return 92 + intro + panel_height
    if kind in {"timeline", "process"}:
        row_heights = [max(timeline_item_required_height(item, 19) for item in row) for row in process_rows(items)]
        panel_height = 44 + sum(row_heights) + max(0, len(row_heights) - 1) * 20
        return 92 + intro + panel_height
    if kind == "comparison":
        card_height = max(card_required_height(item, 39) for item in items)
        return 92 + intro + 48 + card_height
    if kind == "metrics":
        cols = min(4, len(items)); row_heights = [max(metric_required_height(item, 20) for item in items[start:start+cols]) for start in range(0, len(items), cols)]
        return 92 + intro + 46 + sum(row_heights) + max(0, len(row_heights) - 1) * 18
    if kind == "quotes":
        heights = [quote_required_height(item) for item in items]
        return 92 + intro + 44 + sum(heights) + max(0, len(heights) - 1) * 14
    if kind == "synthesis": return 92 + intro + 56 + synthesis_required_height(section)
    raise ValueError(f"unsupported section kind: {kind}")


def render_card(svg: SVG, item: dict, x: int, y: int, w: int, h: int, tone: dict, section_id: str, units: int) -> None:
    group_open(svg, "card", section=section_id, card_id=item["id"], source_segment_ids=",".join(item["source_segment_ids"]))
    svg.rect(x,y,w,h,WHITE,stroke=tone["line"],sw=2,rx=8); svg.rect(x,y,8,h,tone["line"],rx=4)
    draw_icon(svg,x+26,y+19,item.get("icon","list"),tone)
    svg.multiline(x+59,y+40,wrap(item["title"],units-4),22,line_h=26,weight=700,role="card-title")
    if item.get("tag"):
        tw=max(58,18+int(visual_len(item["tag"])*14)); svg.rect(x+w-tw-18,y+18,tw,30,WHITE,stroke=tone["accent"],sw=1,rx=15); svg.text(x+w-tw/2-18,y+39,item["tag"],15,fill=tone["accent"],anchor="middle")
    cursor=y+82
    for bullet in item.get("bullets",[]):
        svg.add('<g data-role="bullet">'); count=emphasized_lines(svg,x+28,cursor,bullet,item.get("emphasis",[]),tone,units,size=17,line_h=24,bullet=True); svg.add('</g>'); cursor+=count*24+6
    takeaway=item.get("takeaway")
    if takeaway:
        takeaway_lines=wrap(takeaway,units+2); strip_h=max(46,len(takeaway_lines)*18+16); strip_y=y+h-strip_h-18
        svg.rect(x+24,strip_y,w-48,strip_h,tone["strip"],rx=7); svg.multiline(x+38,strip_y+26,takeaway_lines,16,line_h=18,weight=600,fill=tone["accent"],role="takeaway")
    svg.add("</g>")


def render_cards(svg: SVG, section: dict, top: int, body_h: int, tone: dict) -> None:
    items=section["items"]; cols=4 if len(items)==4 else min(3,max(1,len(items))); rows=math.ceil(len(items)/cols); gap=18; inner=28
    panel_h=body_h-58; svg.rect(58,top,1564,panel_h,tone["tint"],rx=18)
    card_w=int((1564-2*inner-(cols-1)*gap)/cols); units=18 if cols==4 else 26 if cols==3 else 40
    row_heights=card_row_heights(items,cols,units); row_tops=[]; cursor=top+23
    for row_h in row_heights:
        row_tops.append(cursor); cursor+=row_h+20
    for i,item in enumerate(items):
        row,col=divmod(i,cols); render_card(svg,item,58+inner+col*(card_w+gap),row_tops[row],card_w,row_heights[row],tone,section["id"],units)


def render_comparison(svg: SVG, section: dict, top: int, body_h: int, tone: dict) -> None:
    """Render a genuine two-sided contrast, distinct from parallel concept cards."""
    left, right = section["items"]
    panel_h = body_h - 58
    svg.rect(58, top, 1564, panel_h, tone["tint"], rx=18)
    card_y, card_h, card_w = top + 24, max(card_required_height(item, 39) for item in section["items"]), 690
    left_x, right_x = 88, 902
    render_card(svg, left, left_x, card_y, card_w, card_h, tone, section["id"], 39)
    render_card(svg, right, right_x, card_y, card_w, card_h, tone, section["id"], 39)
    center_x = 840
    svg.line(center_x, card_y + 20, center_x, card_y + card_h - 20, tone["line"], 3)
    svg.circle(center_x, card_y + card_h / 2, 34, tone["accent"])
    svg.text(center_x, card_y + card_h / 2 + 7, "对照", 17, weight=700, fill=WHITE, anchor="middle")


def render_timeline(svg: SVG, section: dict, top: int, body_h: int, tone: dict) -> None:
    items=section["items"]; panel_h=body_h-58; svg.rect(58,top,1564,panel_h,tone["tint"],rx=18)
    chunks=process_rows(items); row_heights=[max(timeline_item_required_height(item,19) for item in chunk) for chunk in chunks]; y0=top+22
    for row,(chunk,row_h) in enumerate(zip(chunks,row_heights)):
        x0=88; svg.rect(x0,y0,1504,row_h,WHITE,stroke=tone["line"],sw=2,rx=8); line_y=y0+52; svg.line(x0+30,line_y,x0+1470,line_y,tone["accent"],2)
        col_w=1504/len(chunk)
        for col,item in enumerate(chunk):
            x=int(x0+col*col_w+18); group_open(svg,"timeline-item",section=section["id"],source_segment_ids=",".join(item["source_segment_ids"])); svg.circle(x+10,line_y,7,tone["accent"]); title_lines=wrap(item["title"],19); svg.multiline(x,y0+94,title_lines,21,line_h=25,weight=700,role="card-title"); cursor=y0+94+len(title_lines)*25+13
            for bullet in item.get("bullets",[]):
                svg.add('<g data-role="bullet">'); count=emphasized_lines(svg,x,cursor,bullet,item.get("emphasis",[]),tone,19,size=16,line_h=23,bullet=True); svg.add('</g>'); cursor+=count*23+8
            if item.get("takeaway"):
                takeaway_lines=wrap(item["takeaway"],19); strip_h=max(40,len(takeaway_lines)*18+16); strip_y=y0+row_h-strip_h-18
                svg.rect(x,strip_y,int(col_w)-36,strip_h,tone["strip"],rx=6); svg.multiline(x+12,strip_y+24,takeaway_lines,14,line_h=18,weight=600,fill=tone["accent"],role="takeaway")
            svg.add("</g>")
        y0+=row_h+20


def render_metrics(svg: SVG, section: dict, top: int, body_h: int, tone: dict) -> None:
    items=section["items"]; cols=min(4,len(items)); panel_h=body_h-58; svg.rect(58,top,1564,panel_h,tone["tint"],rx=18); gap=18; inner=28; w=int((1564-2*inner-(cols-1)*gap)/cols); row_heights=[max(metric_required_height(item,20) for item in items[start:start+cols]) for start in range(0,len(items),cols)]; row_tops=[]; cursor=top+23
    for row_h in row_heights: row_tops.append(cursor); cursor+=row_h+18
    for i,item in enumerate(items):
        row,col=divmod(i,cols); x=58+inner+col*(w+gap); y=row_tops[row]; h=row_heights[row]; group_open(svg,"metric",section=section["id"],source_segment_ids=",".join(item["source_segment_ids"])); svg.rect(x,y,w,h,WHITE,stroke=tone["line"],sw=2,rx=5); svg.rect(x,y,7,h,tone["line"]); label_lines=wrap(item["label"],20); value_lines=wrap(item["value"],20); value_y=y+36+len(label_lines)*21+12; note_y=value_y+len(value_lines)*26+10; svg.multiline(x+25,y+36,label_lines,19,line_h=21,weight=700,role="card-title"); svg.multiline(x+25,value_y,value_lines,23,line_h=26,weight=700,fill=tone["accent"],role="body");
        if item.get("note"): svg.multiline(x+25,note_y,wrap(item["note"],22),16,line_h=20,fill=MUTED,role="body")
        svg.add("</g>")


def render_quotes(svg: SVG, section: dict, top: int, body_h: int, tone: dict) -> None:
    svg.rect(58,top,1564,body_h-58,tone["tint"],rx=18); y=top+22
    for item in section["items"]:
        lines=wrap(item["quote"],62); h=quote_required_height(item); group_open(svg,"quote",section=section["id"],source_segment_ids=",".join(item["source_segment_ids"])); svg.rect(88,y,1504,h,WHITE,stroke=tone["line"],sw=2,rx=8); svg.rect(88,y,8,h,tone["accent"],rx=4); svg.text(116,y+43,"“",34,weight=700,fill=tone["accent"]); svg.multiline(154,y+39,lines,18,line_h=25,weight=500,role="body"); svg.add("</g>"); y+=h+14


def render_synthesis(svg: SVG, section: dict, top: int, body_h: int, tone: dict) -> None:
    card_h=synthesis_required_height(section); group_open(svg,"synthesis",section=section["id"],source_segment_ids=",".join(section["source_segment_ids"])); svg.rect(58,top,1564,body_h-58,tone["tint"],rx=18); svg.rect(88,top+28,1504,card_h,WHITE,stroke=tone["line"],sw=2,rx=8); svg.circle(120,top+70,9,tone["accent"]); svg.multiline(150,top+72,wrap(section["text"],76),18,line_h=28,weight=500,role="body"); svg.add("</g>")


def render_adaptive(model: dict) -> str:
    minutes=model["minutes"]; sections=minutes["sections"]
    heights=[section_height(s) for s in sections]; height=250+sum(heights)+70
    svg=SVG(height); svg.text(78,98,minutes["title"],48,weight=700,role="title"); svg.multiline(78,143,wrap(minutes["subtitle"],69),21,line_h=27,fill=MUTED,role="subtitle"); svg.line(78,205,1602,205,RULE,4)
    y=270
    for index,(section,total_h) in enumerate(zip(sections,heights)):
        tone_name,tone=tone_for(section,index); group_open(svg,"section",section=section["id"],kind=section["kind"],tone=tone_name); svg.rect(78,y-26,44,9,tone["strip"],rx=2); svg.text(78,y,f"{index+1:02d}.",30,weight=700,fill=tone["accent"],role="section-title"); svg.text(132,y,section["title"],30,weight=700,role="section-title"); top=y+34
        if section.get("intro"):
            svg.multiline(78,top+24,wrap(section["intro"],76),17,line_h=24,fill=MUTED,role="section-intro"); top+=54
        body_h=total_h-(top-y)
        kind=section["kind"]
        if kind in {"cards","key_points"}: render_cards(svg,section,top,body_h,tone)
        elif kind=="comparison": render_comparison(svg,section,top,body_h,tone)
        elif kind in {"timeline","process"}: render_timeline(svg,section,top,body_h,tone)
        elif kind=="metrics": render_metrics(svg,section,top,body_h,tone)
        elif kind=="quotes": render_quotes(svg,section,top,body_h,tone)
        elif kind=="synthesis": render_synthesis(svg,section,top,body_h,tone)
        svg.add("</g>"); y+=total_h
    svg.text(840,height-30,"AI 纪要 · 图文摘要",15,fill="#B4B8BD",anchor="middle")
    return svg.finish()


def render(model: dict) -> str:
    return render_adaptive(model)


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--input",type=Path,required=True); parser.add_argument("--output",type=Path,required=True); args=parser.parse_args(); model=json.loads(args.input.read_text(encoding="utf-8")); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(render_adaptive(model),encoding="utf-8"); ET.parse(args.output); print(args.output.resolve())


if __name__=="__main__": main()
