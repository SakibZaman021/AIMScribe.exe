"""The one figure CMED needs: three signals across a single consultation."""
from genfigs import Fig, ACCENT

f = Fig(680, 610,
        "The three signals CMED sends across one consultation. The trigger starts the "
        "recording. Patient information follows once it is running. The "
        "prescription-built signal arms the recording but does not stop it, so "
        "counselling after the printout is still captured. The next patient's trigger "
        "stops the previous recording and starts the new one at the same instant.")

f.text(24, 26, "One consultation, three signals from CMED", size=12.5, bold=True)
f.text(24, 44, "The microphone is open continuously from the first trigger to the "
               "next patient's trigger.", size=9.5)

ROWS = [
    (68,  True,  "API 1 · Trigger",
     "patient_id · doctor_id · hospital_id · start_time · date",
     "Recording starts immediately"),
    (152, True,  "API 2 · Patient information",
     "paramedic tests, notes, demographics — and the previous",
     "prescription if this patient has been here before"),
    (236, False, "Consultation",
     "no signal — the recording simply runs", None),
    (320, True,  "API 3 · Prescription built",
     "ARMS the recording. It does NOT stop it.", None),
    (404, False, "Counselling after the printout",
     "1–2 minutes — still recording, and this is the point", None),
    (488, True,  "API 1 · Next patient",
     "previous recording stops, new one starts at the same",
     "instant — no gap between the two"),
]

for y, is_api, title, l2, l3 in ROWS:
    lines = [(title, 11, True, ACCENT if is_api else "currentColor"), (l2, 9)]
    if l3:
        lines.append((l3, 9))
    f.box(120, y, 520, 68 if l3 else 56, lines,
          color=ACCENT if is_api else "currentColor",
          sw=1.8 if is_api else 1.3,
          dash=None if is_api else "5 4")

for y in (124, 208, 292, 376, 460):
    f.path(f"M380,{y} L380,{y+16}")

# the recording bracket
f.path("M96,68 L84,68 L84,544 L96,544", arrow=False, color=ACCENT, sw=2.2)
f.text(24, 300, "RECORDING", size=9, bold=True, color=ACCENT)
f.text(24, 313, "open", size=9, color=ACCENT)
f.text(24, 326, "throughout", size=9, color=ACCENT)

f.text(24, 578, "Printing the prescription is not the end of the consultation.",
       size=10, bold=True, color=ACCENT)
f.text(24, 594, "That is why API 3 arms the recording instead of stopping it.",
       size=10)
f.write("cmed_fig_signals.svg")
