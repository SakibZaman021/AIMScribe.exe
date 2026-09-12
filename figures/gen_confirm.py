"""Two messages leave CMED at the same moment by two routes; our server matches them."""
from genfigs import Fig, ACCENT

f = Fig(680, 560,
        "Trigger confirmation. When the doctor opens a patient, the CMED page sends "
        "the trigger to the recorder on the same PC and CMED's server sends patient "
        "information to the AIMS LAB server, both carrying the same five fields. The "
        "recorder asks the AIMS LAB server for permission; the server confirms the "
        "recording only if a matching notice from CMED's server exists.")

f.text(24, 26, "Two messages, two routes, one match", size=12.5, bold=True)
f.text(24, 44, "A recording is confirmed only when both copies of the same five "
               "fields meet at our server.", size=9.5)

f.box(230, 64, 220, 44, [("Doctor opens patient details", 10.5, True)])

# route A
f.box(24, 160, 250, 60, [("CMED page", 10.5, True),
                         ("same PC as the recorder", 8.5)])
f.box(24, 290, 250, 60, [("aimscribe.exe", 10.5, True),
                         ("microphone opens at once", 8.5)])
f.path("M290,108 L150,108 L150,154", color=ACCENT, sw=2)
f.path("M150,220 L150,284", color=ACCENT, sw=2)
f.text(160, 246, "1 · trigger", size=9, bold=True, color=ACCENT)
f.text(160, 259, "5 fields", size=9, color=ACCENT)

# route B
f.box(406, 160, 250, 60, [("CMED server", 10.5, True),
                          ("knows the doctor opened it", 8.5)])
f.path("M390,108 L531,108 L531,154", color=ACCENT, sw=2)

# AIMS server
f.box(236, 410, 420, 76, [("AIMS LAB server", 11, True),
                          ("holds the notice for a few minutes", 8.5),
                          ("matches: hospital · doctor · patient · start time", 8.5)],
      sw=2.2)
f.path("M531,220 L531,404", color=ACCENT, sw=2)
f.text(541, 300, "2 · patient information", size=9, bold=True, color=ACCENT)
f.text(541, 313, "same 5 fields", size=9, color=ACCENT)
f.text(541, 326, "+ demographics", size=9, color=ACCENT)

f.path("M150,350 L150,448 L230,448")
f.text(160, 380, "3 · may I record?", size=9, bold=True)
f.text(160, 393, "same 5 fields", size=9)

f.text(24, 516, "Match found — recording confirmed, and linked to its patient "
                "information.", size=10, bold=True)
f.text(24, 534, "No match — recording continues, marked unconfirmed, kept out of "
                "the dataset.", size=10)
f.write("cmed_fig_confirm.svg")
