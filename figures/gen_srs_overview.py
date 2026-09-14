"""SRS Figure 1: the whole system on one page, as planned on 13 September 2026."""
from genfigs import Fig, ACCENT

f = Fig(680, 690,
        "AIMScribe at a glance. The CMED page tells the recorder on the same PC when a "
        "consultation starts and when its prescription is built (Channel A). The CMED "
        "server sends patient information and prescriptions to the UIU server (Channel "
        "B). The recorder uploads audio pieces to Cloudflare R2. The UIU server reads "
        "them back, merges each consultation into a WAV and JSON on its archive, and "
        "stores a lossless FLAC copy in a locked R2 bucket. Audio never goes to CMED.")

f.text(24, 26, "AIMScribe at a glance", size=12.5, bold=True)
f.text(24, 42, "Who sends what, and where the audio goes.", size=9.5)

# ---- consulting-room PC
f.rect(24, 70, 300, 170, rx=8, sw=1.3, dash="5 4", op="0.55")
f.text(24, 64, "CONSULTING-ROOM PC", size=10, bold=True)
f.box(44, 86, 260, 44, [("CMED page in the browser", 10.5, True),
                        ("sends API 1 and API 3 (arm)", 9)])
f.path("M174,130 L174,170", color=ACCENT, sw=2)
f.text(184, 154, "Channel A · same PC", size=9, color=ACCENT, bold=True)
f.box(44, 176, 260, 48, [("aimscribe.exe", 11, True),
                         ("records · encrypts · uploads · Stop/Pause", 9)])

# ---- CMED server
f.box(416, 86, 220, 56, [("CMED server", 11, True),
                         ("API 2 · patient information", 9),
                         ("API 3 · prescription", 9)])
f.path("M636,114 L660,114 L660,470 L642,470", color=ACCENT, sw=2)
f.text(650, 200, "Channel B", size=9.5, bold=True, color=ACCENT, anchor="end")
f.text(650, 214, "HTTPS + API key", size=9, color=ACCENT, anchor="end")

# ---- Cloudflare R2
f.rect(24, 300, 612, 84, rx=8, sw=1.3, dash="5 4", op="0.55")
f.text(636, 294, "CLOUDFLARE R2 · CLOUD STORAGE", size=10, bold=True, anchor="end")
f.box(44, 316, 270, 52, [("Segment bucket", 10.5, True),
                         ("audio pieces · deleted after merge and copy", 9)])
f.box(346, 316, 270, 52, [("Copy bucket · locked", 10.5, True, ACCENT),
                          ("one lossless FLAC per consultation, kept", 9)])

f.path("M114,224 L114,310")
f.text(124, 272, "audio pieces", size=9)
f.path("M304,200 L330,200 L330,444")
f.text(338, 272, "requests", size=9)
f.path("M290,368 L290,444")
f.text(282, 412, "read back · check · merge", size=9, anchor="end")
f.path("M500,448 L500,374", color=ACCENT, sw=2)
f.text(510, 412, "FLAC copy", size=9, color=ACCENT)

# ---- UIU server
f.rect(24, 450, 612, 176, rx=8, sw=1.3, dash="5 4", op="0.55")
f.text(24, 444, "UIU SERVER", size=10, bold=True)
f.box(44, 468, 176, 52, [("PostgreSQL", 11, True), ("aims_recordings · aims_clinical", 9)])
f.box(242, 468, 176, 52, [("API", 11, True), ("authorise · confirm · verify", 9)])
f.box(440, 468, 176, 52, [("Clinical intake", 10.5, True),
                          ("patient information · prescriptions", 9)])
f.box(44, 546, 176, 52, [("Archive worker", 10.5, True), ("merge pieces · check chain", 9)])
f.box(242, 546, 176, 52, [("Archive array", 10.5, True), ("WAV + JSON, same name", 9)])
f.box(440, 546, 176, 52, [("Cloud-copy worker", 10.5, True),
                          ("FLAC · check · encrypt · upload", 9)])
f.path("M220,572 L236,572")
f.path("M418,572 L434,572")

f.text(24, 656, "Audio travels only from the PC to Cloudflare R2 and the UIU server. "
       "It is never sent to CMED.", size=9.5)
f.text(24, 672, "Each copy is deleted only after the next place has proved it holds a "
       "good copy (Figure 6).", size=9.5)

f.write("srs_fig_overview.svg")
