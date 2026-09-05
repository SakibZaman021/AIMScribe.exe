"""
Build the submission document: SRS + figures, one self-contained HTML, then PDF.

No markdown library is available here and none is needed - the specification uses
a small, known subset: headings, tables, fenced code, blockquotes, lists, rules,
images and inline emphasis. Anything outside that subset would be a surprise in
our own document, so the converter is deliberately strict rather than general.

Figures are inlined as SVG, so the result is one file with no external
references: it opens on any machine, prints identically, and survives being
emailed to a partner.
"""
from __future__ import annotations

import html
import os
import re
from pathlib import Path

ROOT = Path(r"C:/Users/USER/Downloads/AIMScribe")
SRC = ROOT / "AIMSCRIBE_SRS.md"
FIGS = ROOT / "figures"
OUT = ROOT / "dist"


# ------------------------------------------------------------- inline markup

def inline(t: str) -> str:
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<a href='\2'>\1</a>", t)
    return t


def svg_of(path: str) -> str:
    p = FIGS / Path(path).name
    if not p.is_file():
        return f"<p class='missing'>[figure not found: {html.escape(path)}]</p>"
    s = p.read_text(encoding="utf-8")
    s = re.sub(r"<\?xml.*?\?>", "", s, flags=re.S).strip()
    return s


# --------------------------------------------------------------- block parse

def convert(md: str) -> str:
    lines = md.split("\n")
    out, i, n = [], 0, len(lines)

    while i < n:
        ln = lines[i]

        # fenced code
        if ln.startswith("```"):
            j = i + 1
            body = []
            while j < n and not lines[j].startswith("```"):
                body.append(lines[j]); j += 1
            out.append("<pre><code>" + html.escape("\n".join(body)) + "</code></pre>")
            i = j + 1
            continue

        # figure image on its own line
        m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)\s*$", ln)
        if m:
            cap = ""
            k = i + 1
            while k < n and not lines[k].strip():
                k += 1
            if k < n and lines[k].startswith("**Figure"):
                cap = inline(lines[k]); i = k
            out.append("<figure>" + svg_of(m.group(2)) +
                       (f"<figcaption>{cap}</figcaption>" if cap else "") + "</figure>")
            i += 1
            continue

        # heading
        m = re.match(r"(#{1,6})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue

        # horizontal rule
        if re.match(r"^-{3,}\s*$", ln):
            out.append("<hr>")
            i += 1
            continue

        # table
        if ln.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|\s*$", lines[i + 1]):
            head = [c.strip() for c in ln.strip().strip("|").split("|")]
            rows, j = [], i + 2
            while j < n and lines[j].startswith("|"):
                rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                j += 1
            t = ["<div class='tw'><table><thead><tr>"]
            t += [f"<th>{inline(c)}</th>" for c in head]
            t.append("</tr></thead><tbody>")
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t))
            i = j
            continue

        # blockquote - requirements live here, so they get their own treatment
        if ln.startswith(">"):
            body, j = [], i
            while j < n and (lines[j].startswith(">") or
                             (not lines[j].strip() and j + 1 < n and
                              lines[j + 1].startswith(">"))):
                body.append(re.sub(r"^>\s?", "", lines[j])); j += 1
            out.append("<blockquote>" + convert("\n".join(body)) + "</blockquote>")
            i = j
            continue

        # lists
        if re.match(r"^\s*[-*]\s+", ln) or re.match(r"^\s*\d+\.\s+", ln):
            ordered = bool(re.match(r"^\s*\d+\.\s+", ln))
            items, j = [], i
            while j < n and (re.match(r"^\s*[-*]\s+", lines[j]) or
                             re.match(r"^\s*\d+\.\s+", lines[j])):
                items.append(re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", lines[j])); j += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) +
                       f"</{tag}>")
            i = j
            continue

        if not ln.strip():
            i += 1
            continue

        # paragraph
        para, j = [], i
        while j < n and lines[j].strip() and not re.match(
                r"^(#{1,6}\s|\||>|```|!\[|-{3,}\s*$|\s*[-*]\s+|\s*\d+\.\s+)", lines[j]):
            para.append(lines[j]); j += 1
        out.append("<p>" + inline(" ".join(para)) + "</p>")
        i = j if j > i else i + 1

    return "\n".join(out)


CSS = """
@page { size: A4; margin: 17mm 15mm 16mm 15mm; }
* { box-sizing: border-box; }
body { font: 10.5pt/1.5 Georgia,"Times New Roman",serif; color:#141414;
       background:#fff; margin:0; padding:0 6mm; }
h1,h2,h3,h4,h5,th { font-family:"Helvetica Neue",Helvetica,Arial,sans-serif; }
h1 { font-size:23pt; line-height:1.15; margin:0 0 4mm; letter-spacing:-.01em; }
h2 { font-size:15pt; margin:0 0 3mm; padding-bottom:1.5mm;
     border-bottom:1.2pt solid #141414; page-break-before:always;
     page-break-after:avoid; }
h2.first { page-break-before:avoid; }
h3 { font-size:12pt; margin:6mm 0 2mm; page-break-after:avoid; }
h4 { font-size:10.5pt; margin:5mm 0 1.5mm; page-break-after:avoid; }
p { margin:0 0 2.6mm; orphans:3; widows:3; }
hr { border:0; border-top:.5pt solid #c8c8c8; margin:5mm 0; }
a { color:#8f1f18; text-decoration:none; }
code { font-family:Consolas,"SF Mono",Menlo,monospace; font-size:.86em;
       background:#f2f0ef; padding:.4mm 1mm; border-radius:1mm; }
pre { background:#f7f5f4; border:.5pt solid #ddd8d6; border-radius:1mm;
      padding:2.5mm 3mm; overflow-x:auto; page-break-inside:avoid; }
pre code { background:none; padding:0; font-size:8.4pt; line-height:1.42; }
.tw { overflow-x:auto; margin:0 0 3.5mm; page-break-inside:avoid; }
table { border-collapse:collapse; width:100%; font-size:8.8pt; }
th,td { border:.5pt solid #cfcac8; padding:1.4mm 2mm; text-align:left;
        vertical-align:top; }
th { background:#f2efee; font-weight:600; font-size:8.4pt; }
blockquote { margin:0 0 3.5mm; padding:2.2mm 0 2.2mm 4mm;
             border-left:2pt solid #b3261e; background:#fbf4f3;
             page-break-inside:avoid; }
blockquote p { margin:0 0 1.6mm; font-size:9.6pt; }
blockquote p:last-child { margin-bottom:0; }
ul,ol { margin:0 0 3mm; padding-left:6mm; }
li { margin-bottom:1.1mm; }
figure { margin:5mm 0; page-break-inside:avoid; text-align:center; }
figure svg { width:100%; height:auto; max-height:215mm; }
figcaption { font-size:8.8pt; text-align:left; margin-top:2.5mm;
             color:#2e2a29; line-height:1.42; }
.missing { color:#b3261e; font-style:italic; }
.cover { page-break-after:always; padding-top:22mm; }
.cover h1 { font-size:29pt; }
.cover .sub { font-size:13pt; color:#3c3735; margin:0 0 12mm; }
.cover table { width:100%; font-size:10pt; }
.cover td { border:0; border-bottom:.5pt solid #ddd8d6; padding:2.2mm 0; }
.cover td:first-child { width:42mm; color:#6b6360; font-family:Helvetica,Arial,
                        sans-serif; font-size:9pt; }
.figindex { margin-top:14mm; }
.figindex td:first-child { width:22mm; }
@media screen { body { max-width:210mm; margin:0 auto; padding:14mm 12mm; }
                h2 { page-break-before:auto; } }
"""


def main() -> None:
    md = SRC.read_text(encoding="utf-8")

    # The cover is built from the front-matter table, then dropped from the body.
    m = re.search(r"^# (.+?)\n(.*?)\n---\n", md, re.S)
    title = m.group(1).strip() if m else "AIMScribe SRS"
    front = m.group(2) if m else ""
    rows = re.findall(r"^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$", front, re.M)
    rows = [(a, b) for a, b in rows if a and not set(a) <= set("- ")]
    body_md = md[m.end():] if m else md

    figs = [(n, cap) for n, cap in
            re.findall(r"\*\*Figure (\d)\.\*\*\s*([^.]+\.)", md)]

    cover = [f"<div class='cover'><h1>{html.escape(title)}</h1>",
             "<p class='sub'>Integration specification for the CMED engineering team"
             "<br>AIMS LAB · Independent University, Bangladesh</p><table>"]
    for a, b in rows:
        cover.append(f"<tr><td>{inline(a)}</td><td>{inline(b)}</td></tr>")
    cover.append("</table>")
    if figs:
        cover.append("<table class='figindex'><tr><td colspan='2'>"
                     "<strong>Figures</strong></td></tr>")
        for n, cap in figs:
            cover.append(f"<tr><td>Figure {n}</td><td>{inline(cap.strip())}</td></tr>")
        cover.append("</table>")
    cover.append("</div>")

    body = convert(body_md)
    body = body.replace("<h2>", "<h2 class='first'>", 1)

    doc = ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
           f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>"
           + "".join(cover) + body + "</body></html>")

    OUT.mkdir(exist_ok=True)
    p = OUT / "AIMScribe_SRS_for_CMED.html"
    p.write_text(doc, encoding="utf-8")
    print(f"  {p.name}  {len(doc)/1024:.0f} KB   "
          f"{doc.count('<svg ')} figures inlined, "
          f"{doc.count('<table')} tables, {doc.count('<blockquote')} requirement blocks")


if __name__ == "__main__":
    main()
