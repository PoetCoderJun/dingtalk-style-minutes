#!/usr/bin/env python3
"""Validate adaptive SVG structure against schema v3 content."""

from __future__ import annotations

import argparse,json,re,sys,xml.etree.ElementTree as ET
from pathlib import Path

def nodes(root,role): return [n for n in root.iter() if n.attrib.get("data-role")==role]
def num(node,attr):
    match=re.search(r"\d+(?:\.\d+)?",node.attrib.get(attr,"0")); return float(match.group()) if match else 0

def compact(text): return re.sub(r"[\s•]+","",str(text))

def text_units(text: str) -> float:
    return sum(1.0 if ord(character) > 255 else 0.56 for character in text)

def positioned_outside(node, width: float, height: float) -> bool:
    """Reject plainly off-canvas native nodes; detailed collision checks stay in whiteboard-cli."""
    tag=node.tag.rsplit("}",1)[-1]
    if tag in {"text","rect"}:
        x,y=num(node,"x"),num(node,"y")
        if x < 0 or y < 0 or x > width or y > height: return True
        if tag=="text":
            size=max(1.0,num(node,"font-size")); anchor=node.attrib.get("text-anchor","start")
            lines=[]
            tspans=[child for child in node if child.tag.rsplit("}",1)[-1]=="tspan"]
            if tspans: lines=["".join(child.itertext()) for child in tspans]
            else: lines=["".join(node.itertext())]
            estimated=max((text_units(line)*size for line in lines),default=0.0)
            left=x-estimated/2 if anchor=="middle" else x-estimated if anchor=="end" else x
            right=x+estimated/2 if anchor=="middle" else x if anchor=="end" else x+estimated
            line_height=size*1.45; bottom=y+max(0,len(lines)-1)*line_height
            if left < -0.5 or right > width+0.5 or bottom > height+0.5: return True
        if tag=="rect" and (x+num(node,"width")>width+0.5 or y+num(node,"height")>height+0.5): return True
    if tag=="circle":
        cx,cy,r=num(node,"cx"),num(node,"cy"),num(node,"r")
        return cx-r < 0 or cy-r < 0 or cx+r > width or cy+r > height
    if tag=="line":
        return any(value < 0 for value in (num(node,"x1"),num(node,"y1"),num(node,"x2"),num(node,"y2"))) or num(node,"x1")>width or num(node,"x2")>width or num(node,"y1")>height or num(node,"y2")>height
    return False

def visible_strings(model):
    minutes=model["minutes"]
    yield minutes["title"]; yield minutes["subtitle"]
    for section in minutes["sections"]:
        yield section["title"]
        if section.get("intro"): yield section["intro"]
        if section["kind"]=="synthesis":
            yield section["text"]
            continue
        for item in section.get("items",[]):
            for key in ("title","tag","takeaway","label","value","note","quote"):
                if item.get(key): yield item[key]
            yield from item.get("bullets",[])

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("svg",type=Path); p.add_argument("--model",type=Path,required=True); a=p.parse_args(); model=json.loads(a.model.read_text(encoding="utf-8")); root=ET.parse(a.svg).getroot(); failures=[]
    vb=[float(x) for x in root.attrib.get("viewBox","").split()]
    if len(vb)!=4 or vb[:3]!=[0,0,1680] or not 1200<=vb[3]<=9000: failures.append(f"adaptive portrait viewBox invalid: {vb}")
    elif any(positioned_outside(node,vb[2],vb[3]) for node in root.iter()): failures.append("native node positioned outside viewBox")
    expected=model["minutes"]["sections"]; rendered=nodes(root,"section")
    if len(rendered)!=len(expected): failures.append(f"section count {len(rendered)} != {len(expected)}")
    actual=[(n.attrib.get("data-section"),n.attrib.get("data-kind")) for n in rendered]; wanted=[(s["id"],s["kind"]) for s in expected]
    if actual!=wanted: failures.append(f"section identity/order mismatch: {actual} != {wanted}")
    provenance=[n for n in root.iter() if n.attrib.get("data-source-segment-ids")]
    if not provenance: failures.append("no source-segment provenance embedded in SVG")
    for section in expected:
        expected_items=1 if section["kind"]=="synthesis" else len(section.get("items",[]))
        got=len([n for n in provenance if n.attrib.get("data-section")==section["id"]])
        if got!=expected_items: failures.append(f"{section['id']}: provenance items {got} != {expected_items}")
    for role,(lo,hi) in {"title":(42,50),"subtitle":(18,23),"section-title":(26,32),"card-title":(18,25),"body":(14,23)}.items():
        found=nodes(root,role)
        if not found: failures.append(f"missing {role}")
        bad=[num(n,"font-size") for n in found if not lo<=num(n,"font-size")<=hi]
        if bad: failures.append(f"{role} sizes outside {lo}-{hi}: {bad[:8]}")
    expected_emphasis=[phrase for section in expected if section["kind"] in {"cards","key_points","timeline","process","comparison"} for item in section.get("items",[]) for phrase in item.get("emphasis",[])]
    rendered_emphasis=nodes(root,"body-emphasis")
    if sorted("".join(node.itertext()) for node in rendered_emphasis)!=sorted(expected_emphasis): failures.append("semantic emphasis spans do not match model")
    if any(node.attrib.get("font-weight")!="700" for node in rendered_emphasis): failures.append("semantic emphasis must be bold")
    forbidden={"filter","linearGradient","radialGradient","pattern","clipPath","mask","polygon"}; used={n.tag.rsplit("}",1)[-1] for n in root.iter()}
    if forbidden&used: failures.append("unsupported tags: "+", ".join(sorted(forbidden&used)))
    svg_text=compact("".join(root.itertext()))
    missing=[value for value in visible_strings(model) if compact(value) not in svg_text]
    if missing: failures.append(f"model text missing or truncated in SVG: {missing[:5]}")
    if failures: print("FAIL"); print("\n".join(f"- {x}" for x in failures)); return 1
    print(f"PASS: adaptive portrait, {len(expected)} sections, {len(provenance)} traceable items"); return 0

if __name__=="__main__": sys.exit(main())
