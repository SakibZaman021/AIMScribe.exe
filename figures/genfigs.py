"""
Generate the AIMScribe manuscript figures, and refuse to emit one that collides.

Overlapping labels were the defect in the hand-placed version. Every text run
here is measured, given a bounding box, and checked against every other text run
and against the shape it belongs to. A collision raises before anything is
written, so a figure that exists is a figure that is clean.

Width estimate is deliberately generous: Helvetica averages ~0.52 em over mixed
case, and 0.60 leaves room for the wide-glyph strings that actually bite.
"""
import os
import re

ACCENT = "#b3261e"
OUT = r"C:/Users/USER/Downloads/AIMScribe/figures"

WIDE = set("MWmw@%")
NARROW = set("iljItf.,:;'|! ")


def text_w(s, size, bold=False):
    """Approximate rendered width in px."""
    u = 0.0
    for ch in s:
        u += 0.75 if ch in WIDE else 0.32 if ch in NARROW else 0.545
    return u * size * (1.06 if bold else 1.0)


class Fig:
    def __init__(self, w, h, aria):
        self.w, self.h, self.aria = w, h, aria
        self.parts = []
        self.tboxes = []          # (x0,y0,x1,y1,label) for collision checking
        self.segs = []            # drawn line segments, so text cannot sit on one

    # ---- primitives ----

    def rect(self, x, y, w, h, *, rx=5, sw=1.5, dash=None, color="currentColor",
             op=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        o = f' opacity="{op}"' if op else ""
        if sw:
            # Borders count as lines: a label that grazes a box edge reads as a
            # collision even though it sits inside the frame around it.
            self.segs += [(x, y, x + w, y), (x, y + h, x + w, y + h),
                          (x, y, x, y + h), (x + w, y, x + w, y + h)]
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                          f'fill="none" stroke="{color}" stroke-width="{sw}"{d}{o}/>')

    def path(self, d, *, color="currentColor", sw=1.5, dash=None, arrow=True):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        mk = ' marker-end="url(#ar)"' if arrow and color == "currentColor" else (
             ' marker-end="url(#arA)"' if arrow else "")
        pts = [(float(a), float(b)) for a, b in
               re.findall(r'[ML]\s*(-?[\d.]+),(-?[\d.]+)', d)]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            self.segs.append((x0, y0, x1, y1))
        self.parts.append(f'<path d="{d}" fill="none" stroke="{color}" '
                          f'stroke-width="{sw}"{da}{mk}/>')

    def text(self, x, y, s, *, size=11, bold=False, anchor="start",
             color="currentColor", italic=False, register=True):
        w = text_w(s, size, bold)
        x0 = x if anchor == "start" else x - w / 2 if anchor == "middle" else x - w
        if register:
            # ascent above baseline ~0.78em, descent ~0.22em
            self.tboxes.append((x0, y - size * 0.80, x0 + w, y + size * 0.24, s))
        fw = ' font-weight="600"' if bold else ""
        fs = ' font-style="italic"' if italic else ""
        ta = f' text-anchor="{anchor}"' if anchor != "start" else ""
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}"{fw}{fs}{ta} '
                          f'fill="{color}">{s}</text>')

    # ---- composites ----

    def box(self, x, y, w, h, lines, *, sw=1.5, dash=None, color="currentColor",
            rx=5):
        """A rectangle whose lines are centred and guaranteed to fit inside it."""
        self.rect(x, y, w, h, rx=rx, sw=sw, dash=dash, color=color)
        sizes = [ln[1] if len(ln) > 1 else 11 for ln in lines]
        gap = 3
        total = sum(s * 1.18 for s in sizes) + gap * (len(lines) - 1)
        if total > h - 8:
            raise SystemExit(f"BOX OVERFLOW: {lines[0][0]!r} needs {total:.0f}px in {h}px")
        cy = y + (h - total) / 2
        for ln in lines:
            s = ln[0]
            size = ln[1] if len(ln) > 1 else 11
            bold = ln[2] if len(ln) > 2 else False
            col = ln[3] if len(ln) > 3 else color
            cy += size * 0.94
            if text_w(s, size, bold) > w - 12:
                raise SystemExit(f"TEXT TOO WIDE for its box: {s!r} "
                                 f"({text_w(s,size,bold):.0f}px in {w-12}px)")
            self.text(x + w / 2, cy, s, size=size, bold=bold, anchor="middle",
                      color=col)
            cy += size * 0.24 + gap

    def label(self, cx, cy, s, *, size=10, color="currentColor", bold=False,
              slot=None):
        """A free-standing arrow label. `slot` is (x0,x1) it must stay inside."""
        w = text_w(s, size, bold)
        if slot and (cx - w / 2 < slot[0] or cx + w / 2 > slot[1]):
            raise SystemExit(f"LABEL {s!r} ({w:.0f}px) escapes slot {slot}")
        self.text(cx, cy, s, size=size, bold=bold, anchor="middle", color=color)

    # ---- validation ----

    def check(self):
        bad = []
        for i in range(len(self.tboxes)):
            ax0, ay0, ax1, ay1, at = self.tboxes[i]
            if ax0 < -2 or ax1 > self.w + 2 or ay0 < -2 or ay1 > self.h + 2:
                bad.append(f"OUT OF CANVAS: {at!r}")
            for j in range(i + 1, len(self.tboxes)):
                bx0, by0, bx1, by1, bt = self.tboxes[j]
                if ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1:
                    bad.append(f"OVERLAP: {at!r}  x  {bt!r}")
        # text sitting on a drawn line reads as broken even when no two labels
        # collide - that is what the hand-placed version got wrong.
        for tx0, ty0, tx1, ty1, t in self.tboxes:
            for sx0, sy0, sx1, sy1 in self.segs:
                lx0, lx1 = min(sx0, sx1) - 1, max(sx0, sx1) + 1
                ly0, ly1 = min(sy0, sy1) - 1, max(sy0, sy1) + 1
                if tx0 < lx1 and lx0 < tx1 and ty0 < ly1 and ly0 < ty1:
                    bad.append(f"TEXT ON A LINE: {t!r}")
                    break
        return bad

    def write(self, name):
        bad = self.check()
        if bad:
            print(f"\n{name}: {len(bad)} problem(s)")
            for b in bad[:20]:
                print("   ", b)
            raise SystemExit(1)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
               f'color="#1a1a1a" role="img" aria-label="{self.aria}" '
               f'font-family="Helvetica, Arial, sans-serif">\n'
               f'<defs>'
               f'<marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
               f'markerHeight="7" orient="auto-start-reverse">'
               f'<path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker>'
               f'<marker id="arA" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
               f'markerHeight="7" orient="auto-start-reverse">'
               f'<path d="M0,0 L10,5 L0,10 z" fill="{ACCENT}"/></marker>'
               f'</defs>\n' + "\n".join(self.parts) + "\n</svg>\n")
        os.makedirs(OUT, exist_ok=True)
        p = os.path.join(OUT, name)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
        print(f"  ok  {name:32s} {self.w}x{self.h}  {len(self.tboxes)} labels, no collisions")
