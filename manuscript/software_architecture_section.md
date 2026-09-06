## Software Architecture and Data Collection System

### System Architecture and Interoperability

AIMScribe was developed not as a clinical application but as an event-driven,
decentralised agent architecture, in which each consulting room operates as an
autonomous node. The endpoint element, `aimscribe.exe`, is a lightweight edge
daemon presented to the clinician only as a system-tray icon. Acquisition,
segmentation and transmission run on independent threads and an asynchronous
transport loop, so that disk and network latency cannot propagate back into
the audio path. This separation is a deployment requirement, not an
optimisation: the study sites run legacy, lower-specification workstations on
which any blocking operation would degrade the electronic health record (EHR)
in active use. Audio is acquired as linear PCM at the capture device's native
sample rate, with operating-system resampling and channel down-mixing excluded
from the path, at a sustained 88.2 kB s⁻¹.

The interoperability layer is agnostic to the partner record system. Rather
than requiring each vendor to integrate with a remote service, it is exposed
as a loopback interface on the clinician's workstation, addressed by a small
quantity of JavaScript within the existing EHR page. One contract is therefore
implemented identically for the three partner systems in the deployment —
CMED, Aalo and Amader Susastho — none of which holds cryptographic material,
stores audio, exposes an endpoint, or alters its server infrastructure. The
architecture admits no inbound connection from a partner system to the
research backend; all traffic crossing an organisational boundary originates
within the clinic.

[Insert Figure X: Architecture block diagram delineating the trust boundaries
between the local workstation, the partner EHR node and the AIMS Lab backend,
and showing that the integration surface is confined to a loopback channel on
the clinician's own machine.]

### Zero-Touch Trigger Mechanism and Acoustic Pre-processing

Acquisition imposes no interface burden on the consultation. Requiring a
clinician to start and stop a recorder introduces cognitive load when
attention is owed to the patient, and such controls are reliably forgotten.
The trigger is therefore derived from an action already performed: an EHR
interface event, the selection of patient details, dispatches a signal over
the loopback channel to the local daemon, and background capture begins.
Authorisation is obtained from the backend in parallel with acquisition rather
than before it. Transient network latency thus cannot displace the opening
seconds of the encounter, in which the presenting complaint is typically
stated.

Triggering is synchronised with a fixed acoustic configuration in each room,
necessary because the enclosures are acoustically hostile: ceiling fans,
corridor traffic and paediatric distress are continuous rather than
intermittent. Segment boundaries are placed using short-term root-mean-square
energy together with zero-crossing rate, evaluated against an adaptive noise
floor so that the criterion tracks the room rather than assuming a fixed
threshold. The zero-crossing term keeps boundaries out of unvoiced fricatives,
which carry low energy and mimic pauses. Silence positions boundaries but is
never excised: the archived recording is retained bit-identical to the
acquired signal. Material for downstream speech recognition and diarisation is
derived from that archive as a separate, disposable rendition.

Characterisation of the deployed hardware proved consequential. Conferencing
speakerphones applying vendor noise suppression were found to gate quiet
interlocutors, reducing 8.7% of frames to digital silence. On affected units
the quieter speaker was attenuated to −56 to −69 dBFS, against −36 to −42 dBFS
on correctly configured units; the louder speaker was unaffected. Because
patients speak more quietly and at greater distance than clinicians, such
processing removes precisely the signal of interest. Specification of the
acquisition path was consequently treated as a measured commissioning
requirement rather than a procurement detail.

[Insert Figure Y: UML sequence diagram of the trigger-to-upload flow, from the
EHR interface event through parallel authorisation, segment sealing,
server-side verification and purge receipt, to archival.]

### Network Fault Tolerance and Edge Caching

Connectivity across the study sites is intermittent, and the acquisition path
was therefore made offline-first rather than offline-tolerant. Each sealed
segment is encrypted under AES-256-GCM and committed to a local spool before
transmission is attempted. Every state transition is appended to a
synchronously flushed journal, so that abrupt power loss cannot render a
partial segment indistinguishable from a complete one. The spool is
provisioned at 40 GB — approximately 135 recorded hours, or three weeks of a
room's activity without connectivity. Synchronisation is opportunistic: when
bandwidth returns, queued segments are transmitted in chain order by a
background loop decoupled from acquisition, so that drainage of an accumulated
backlog does not perturb the consultation in progress.

### Deterministic Data Labelling and Synchronisation

Each archived recording is named under a fixed taxonomy,
`PatientID_DoctorID_HospitalID_StartTime_EndTime_Date`, which functions as a
relational mapping strategy rather than a filing convention. Identifiers are
supplied by the record system at triggering and constrained to a restricted
character set, since they become directory names on the archival volume.
Consultations proceed back-to-back at intervals of twenty to thirty seconds;
the start time of a succeeding encounter is therefore adopted as the end time
of its predecessor, so that recordings tile the session without gap or
overlap. Referential integrity between the audio corpus and the structured
record is thus established at acquisition rather than reconstructed
afterwards. An interlock further withholds session closure until the encounter
has been concluded in the record system. Inadvertent selection of a subsequent
patient therefore cannot truncate an active consultation — a failure mode
observed in pilot operation, and not recoverable afterwards.

### Device Binding and Cryptographic Security

Access to the acquisition path is constrained by hardware-anchored
authentication. Each workstation is commissioned once by an administrator,
using a single-use activation credential exchanged for a device identity and
an asymmetric key pair generated on, and never leaving, that machine; the
backend retains the credential only as a cryptographic digest. Binding is
between workstation and research backend, and is therefore independent of the
partner record system.

Registration establishes that a machine may record at all; a separate
authorisation — short-lived, single-use, issued per encounter and verified
against a pinned public key — establishes that a particular request is
legitimate. The two controls are deliberately distinct: an enrolled
workstation without the second would record for any page loaded in the
clinician's browser. Compromise of EHR access alone therefore confers no
capability to initiate or intercept acquisition.

Integrity is maintained end-to-end by a per-session hash chain. Each entry —
session opening, every segment, every interruption, and closure — embeds the
digest of its predecessor and is signed by the device key, rendering deletion,
reordering and substitution detectable. Segments are verified on arrival by
re-reading the stored object and recomputing its digest server-side. Local
material is released for deletion only against a signed purge receipt
attesting that a verified archival copy exists; any discrepancy quarantines
the session, withholds the receipt and preserves both copies. A continuous
chain of custody is thereby maintained from acquisition to archive, under
which tampering, silent truncation and corruption at rest are detectable
rather than merely improbable.
