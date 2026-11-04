# Memorycam: project scope and next milestone

Updated November 4, 2026.

The core thesis is the daily journaling ritual: an intentional N900 photograph from the day meets a photograph from the personal archive, printed as two separate slips on arriving home. The images themselves are the prompt.

The private owner desk supports immediate phone sharing, uploaded archive photographs and native website-camera capture. These owner phone-to-paper routes have been physically demonstrated.

The third part is a public guest website for the final class presentation and for parties. Guests scan a QR code, write a note, choose a photo from their phone, or take one live. They check a preview and deliberately send it to my printer. It has its own landing page and composer; the private owner desk stays separate. Both belong to Memorycam.

## Implementation and evidence

A separate guest-site package now contains the landing page, note/photo composer, native-camera picker, live bounded JPEG preview, explicit consent and a server-side bridge to the existing private inbox. The same Mac consumer and serialized queue handle output. No personal catalogue, printer network endpoint or owner secret is made public.

Events are closed by default and use expiring QR invitations, a hard fifty-reservation event budget and safe same-ID retries. The browser retains an uncertain preview for retry within the tab. A saved response confirms inbox receipt, not a physical print.

Twelve isolated checks pass, including concurrent event-budget enforcement, invalid inputs, expiry, private boundaries and retry handling. The built Worker validates. The guest build is deployed for owner review with sending closed; public access is pending explicit approval. Taste Skill was expressly authorized for the task; responsive inspection at phone, tablet and desktop widths reports zero failures, with documented visual limitations. Synthetic example-note previews are clearly labelled and are not evidence of received guest messages or physical prints.

## Acceptance before the presentation

- With the owner present, open one short test event and verify a note, a library photograph and a native-camera photograph reach paper exactly as intended.
- Scan the real event QR from another phone, verify closure/expiry and safe retry, and rehearse several guests sharing a network.
- Rehearse the Mac and printer at the destination. The Mac needs to be awake, logged in and online; it must reach the printer on the current network. Moving the printer does not automatically preserve its address or connectivity.
- Prepare the presentation QR and party operating instructions only after that rehearsal.

Daily arrival reliability remains separate: the dual N900/iPhone home-network gate is active and iPhone Wi-Fi absence/return was physically checked. Controlled sleep/ordinary arrival, deep-sleep reliability and the N900 Wi-Fi dropout remain open. Full Google Photos coverage is a separate eventual source goal, with private export-size/storage planning pending.

No guest-route physical print was initiated during this build. The source and runtime data stay outside this public documentation checkout.
