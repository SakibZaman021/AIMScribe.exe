"""SRS Figure 6: where the audio is at each step, and when each copy is deleted."""
from genfigs import Fig, ACCENT

f = Fig(680, 552,
        "Where the audio is, step by step. One: an encrypted piece in the buffer on the "
        "doctor's PC, deleted as soon as the server issues a receipt. Two: the piece in "
        "the Cloudflare R2 segment bucket, deleted only after steps four and five are "
        "verified. Three: the UIU server reads the piece back and checks it. Four: the "
        "UIU archive holds one WAV and one JSON per consultation. Five: a lossless, "
        "encrypted FLAC copy is kept in a locked R2 bucket.")

f.text(24, 26, "Where the audio is, step by step", size=12.5, bold=True)
f.text(24, 42, "Each copy is deleted only after the next place has proved it holds a "
       "good copy.", size=9.5)
f.text(24, 64, "WHERE THE AUDIO IS", size=9.5, bold=True)
f.text(356, 64, "WHEN THIS COPY IS DELETED", size=9.5, bold=True)

rows = [
    ("1 · On the doctor's PC", "encrypted piece in the buffer (AES-256-GCM)",
     ("Immediately, when the server issues a", "receipt for a verified copy."), True),
    ("2 · Cloudflare R2 · segment bucket", "piece uploaded over TLS, encrypted at rest",
     ("Only after steps 4 and 5 are verified", "and recorded in the database."), True),
    ("3 · UIU server checks the piece", "reads it back, re-hashes it, issues a receipt",
     ("A working copy, removed once the", "recording is archived."), False),
    ("4 · UIU archive array", "one WAV + one JSON per consultation, same name",
     ("The original. Kept at UIU; the", "retention period is OD-06."), False),
    ("5 · Cloudflare R2 · copy bucket", "lossless FLAC, checked, encrypted, locked",
     ("Kept, locked against deletion. It can", "rebuild the archive if UIU is lost."), False),
]
arrows = ["upload", "read back", "merge when the consultation closes",
          "compress · check · encrypt · upload"]

Y0, STEP, H = 76, 90, 56
for i, (title, sub, note, accent) in enumerate(rows):
    y = Y0 + i * STEP
    f.box(24, y, 300, H, [(title, 11, True), (sub, 9)])
    col = ACCENT if accent else "currentColor"
    f.text(356, y + 24, note[0], size=9.5, color=col)
    f.text(356, y + 38, note[1], size=9.5, color=col)
    if i < len(arrows):
        f.path(f"M174,{y + H} L174,{y + STEP - 6}")
        f.text(184, y + H + 21, arrows[i], size=9)

f.text(24, 520, "The cloud pieces are deleted only when the recording is complete in two "
       "other places:", size=9.5)
f.text(24, 536, "the UIU archive and the FLAC copy. A failure part way through costs time, "
       "never audio.", size=9.5)

f.write("srs_fig_journey.svg")
