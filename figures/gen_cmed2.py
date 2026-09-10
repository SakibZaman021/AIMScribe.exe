"""Two channels: the local control channel, and the server-to-server data channel."""
from genfigs import Fig, ACCENT

f = Fig(680, 620,
        "The two channels between CMED and AIMScribe. Channel A runs from the CMED "
        "page in the doctor's browser to the recorder on the same machine and carries "
        "only the control signals. Channel B runs server to server from CMED to the "
        "AIMS LAB backend and carries the clinical data. Audio travels only from the "
        "recorder to the AIMS LAB backend and is never sent to CMED.")

f.text(24, 26, "Two channels, two jobs", size=12.5, bold=True)
f.text(24, 44, "Control signals go to the PC. Clinical data goes server to server.",
       size=9.5)

# --- consulting room
f.rect(24, 68, 300, 300, rx=8, sw=1.3, dash="5 4", op="0.55")
f.text(24, 62, "DOCTOR'S PC", size=10, bold=True)
f.box(44, 92, 260, 52, [("CMED page in the browser", 10.5, True),
                        ("sends the control signals", 8.5)])
f.box(44, 196, 260, 68, [("aimscribe.exe", 10.5, True),
                         ("records · encrypts · uploads", 8.5),
                         ("shows Stop / Pause to the doctor", 8.5)])
f.box(44, 292, 260, 52, [("Microphone", 10.5, True),
                         ("fixed placement in the room", 8.5)])
f.path("M174,144 L174,190", color=ACCENT, sw=2.4)
f.path("M174,292 L174,270")
f.text(184, 172, "Channel A", size=9, bold=True, color=ACCENT)

# --- CMED server
f.rect(392, 68, 264, 120, rx=8, sw=1.3, dash="5 4", op="0.55")
f.text(392, 62, "CMED SERVERS", size=10, bold=True)
f.box(412, 92, 224, 76, [("CMED backend", 10.5, True),
                         ("sends patient information", 8.5),
                         ("and prescription contents", 8.5)])

# --- AIMS LAB
f.rect(392, 236, 264, 300, rx=8, sw=1.3, dash="5 4", op="0.55")
f.text(392, 230, "AIMS LAB", size=10, bold=True)
f.box(412, 260, 224, 60, [("Backend API", 10.5, True),
                          ("authorises · verifies · stores", 8.5)])
f.box(412, 344, 224, 56, [("Recordings database", 10.5, True),
                          ("sessions · devices · integrity", 8.5)])
f.box(412, 420, 224, 56, [("Clinical database", 10.5, True),
                          ("prescriptions · notes · history", 8.5)])
f.box(412, 492, 224, 36, [("Audio archive", 10.5, True)])
f.path("M524,320 L524,338")
f.path("M618,320 L618,414")
f.path("M430,320 L430,486")

# --- channel B
f.path("M524,188 L524,254", color=ACCENT, sw=2.4)
f.text(534, 214, "Channel B", size=9, bold=True, color=ACCENT)
f.text(534, 227, "HTTPS + key", size=8.5, color=ACCENT)

# --- audio path
f.path("M304,290 L406,290")
f.text(340, 282, "audio", size=8.5)

f.text(24, 400, "Channel A — to the PC", size=10, bold=True, color=ACCENT)
f.text(24, 416, "API 1 trigger, API 3 arm.", size=9)
f.text(24, 430, "Small, instant, controls", size=9)
f.text(24, 444, "the microphone.", size=9)

f.text(24, 476, "Channel B — to AIMS LAB", size=10, bold=True, color=ACCENT)
f.text(24, 492, "API 2 patient information,", size=9)
f.text(24, 506, "API 3 prescription contents.", size=9)
f.text(24, 520, "Server to server, no browser.", size=9)

f.text(24, 570, "Audio only ever travels from the PC to AIMS LAB.", size=10,
       bold=True)
f.text(24, 586, "It is never sent to CMED, in any form, at any time.", size=10)
f.write("cmed_fig_channels.svg")
