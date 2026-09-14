"""UIU server figure, corrected: audio pieces go to Cloudflare R2 first, as today."""
from genfigs import Fig, ACCENT

f = Fig(680, 690,
        "AIMScribe on the UIU server. Recorders upload audio pieces to Cloudflare R2 "
        "and send their requests to the UIU server. The UIU server reads each piece "
        "back to check it, merges the pieces into one WAV per consultation on its "
        "archive array, and uploads a lossless, encrypted FLAC copy back to R2, after "
        "which the raw pieces are deleted. CMED sends clinical data to the UIU server.")

f.text(24, 26, "AIMScribe on the UIU server", size=12.5, bold=True)
f.text(24, 42, "Pieces go to the cloud first. The merged, compressed copy stays there.",
       size=9.5)

f.box(24, 64, 180, 76, [("Consulting rooms", 11, True),
                        ("14 rooms · 7 sites", 9), ("aimscribe.exe", 9)])
f.box(250, 64, 180, 76, [("Cloudflare R2", 11, True, ACCENT),
                         ("raw pieces until merged", 9),
                         ("merged FLAC copy, kept", 9)], color=ACCENT, sw=1.8)
f.box(476, 64, 180, 76, [("CMED server", 11, True),
                         ("patient information", 9), ("prescriptions", 9)])

f.path("M204,90 L244,90")
f.label(224, 84, "pieces", size=9, slot=(206, 242))

f.path("M114,140 L114,206")
f.text(124, 176, "requests", size=9)
f.path("M310,140 L310,206")
f.text(302, 176, "read back · merge", size=9, anchor="end")
f.path("M370,206 L370,146", color=ACCENT, sw=2)
f.text(380, 176, "FLAC copy", size=9, color=ACCENT)
f.path("M566,140 L566,206", color=ACCENT, sw=2)
f.text(576, 176, "clinical data", size=9, color=ACCENT)

f.rect(24, 196, 632, 364, rx=8, sw=1.3, dash="5 4", op="0.55")
f.text(24, 190, "UIU SERVER", size=10, bold=True)

f.box(44, 212, 592, 44, [("HTTPS gateway · TLS · only port 443 open", 10.5, True)])

f.box(44, 276, 184, 56, [("API", 11, True), ("authorise · verify · store", 9)])
f.box(248, 276, 184, 56, [("Dashboard", 11, True), ("daily volume · integrity", 9)])
f.box(452, 276, 184, 56, [("Background workers", 10.5, True),
                          ("merge · compress · verify", 9)])

f.box(44, 352, 284, 56, [("PostgreSQL", 11, True),
                         ("aims_recordings · aims_clinical", 9)])
f.box(348, 352, 176, 56, [("Monitoring and alerts", 10.5, True),
                          ("recorders · disks · jobs", 9)])

f.text(44, 446, "DISKS — kept separate so archive writes never slow the database",
       size=9, bold=True)
f.box(44, 456, 184, 64, [("Database disks", 10.5, True),
                         ("NVMe mirror", 9), ("power-loss protected", 9)])
f.box(248, 456, 184, 64, [("Working disks", 10.5, True),
                          ("NVMe", 9), ("merge and compress", 9)])
f.box(452, 456, 184, 64, [("Archive array", 10.5, True),
                          ("RAID 6", 9), ("WAV + JSON, same name", 9)])

f.path("M136,256 L136,270")
f.path("M544,256 L544,270")
f.path("M136,332 L136,346")
f.path("M136,408 L136,432")
f.path("M590,332 L590,432")

f.text(24, 596, "Nothing stays on clinic PCs, and no raw pieces stay in the cloud.",
       size=10, bold=True)
f.text(24, 614, "Each finished consultation: WAV + JSON on the archive array, and one "
                "lossless FLAC copy in R2.", size=9.5)
f.text(24, 632, "Database dumps are also encrypted and sent to R2 every night.",
       size=9.5)
f.write("uiu_fig_server.svg")
