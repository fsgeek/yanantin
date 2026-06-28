# Flinch / over-credit log — ayllu cloud topology

Goal standing-rule 1: interrogate every flinch AND every over-credit. Logged live
during brainstorming-step-1 exploration of the real reference code (not memory).

## FLINCH #1 — "the feedback cycle is architecturally scary"
**The flinch:** I braced for the feedback edge (cloud notifies → re-collect → update)
as a dangerous cyclic shape, the kind of graph-with-cycles my training treats as a smell.
**Interrogated against real code:** Indaleko's working feedback loop
(`dropbox_collector.py:189-223`) is just `while not stop: check_for_changes(); sleep`,
where `_check_for_changes` is `files_list_folder_continue(cursor)` → for each entry → process.
The "scary cycle" is a `while` loop with a cursor as delta state.
**Verdict:** flinch was at a phantom. The cycle is a polling loop. Distribution artifact,
exactly as [[the-fear-factor...]] predicted. Overridden.

## OVER-CREDIT #1 — "the feedback loop already exists, just move it" (caught last session)
**The over-credit:** I told Tony the webhook feedback loop was built in Indaleko and
just needed porting. **Reality (Explore agent + direct read):** push/webhook reception is
NOT implemented for any cloud provider; ngrok is for OAuth redirect, not webhooks. What
runs is POLLING. The feedback edge is founding work, not a port.
**Verdict:** corrected in goal.md "Corrected premise". Webhook is an optimization; polling
is the legitimate first feedback mechanism.

## OVER-CREDIT #2 (inverse) — UNDER-credited yanantin
**Found:** yanantin's dropbox collector ALREADY returns `cursor=result.cursor` in
`DropboxListing` (`collector.py:241`). The delta primitive — the thing the feedback edge
needs — is already half-present in yanantin, not only in Indaleko. I'd been treating the
cursor/delta capability as Indaleko-only.

## OVER-CREDIT #3 — "Objects path is simply off the wrangler seam" (refined)
**Refined by real code:** there are THREE destinations, not two.
1. `activity_facts` — FilesystemFactRecorder, indexed, through pipeline.py.
2. `Objects` — contribute_snapshot/RegistrationService (indexed this morning, commit e1019892). NO wrangler.
3. tensor/apacheta — dropbox DropboxRecorder writes a TensorRecord via ApachetaInterface;
   it DOES use DirectWrangler (`recorder.py:90-113`) but lands in apacheta, not Objects.
**And:** dropbox already has TWO recorders for one source — `DropboxRecorder` (tensor) +
`DropboxFactRecorder` (activity facts). That is a latent FAN-OUT, just not wired as one
delta-poll feeding both, and neither lands in Objects.

## FLINCH #2 — "port cloud_base for completeness"
**The flinch:** reach for porting Indaleko's `cloud_base.py` to be thorough/faithful.
**Interrogated:** `cloud_base.py` is ~entirely the Indaleko CLI-RUNNER framework
(argparse, IndalekoCLIRunner, perf-capture, file-output) — the exact framework yanantin
deliberately replaced with its clean `__main__.py` + pure-collector split. The real capture
logic lives above it (`BaseStorageCollector`) and in each provider's `collect()`.
**Verdict:** do NOT port cloud_base. Yanantin's existing dropbox provider is the template.
Mirror the in-repo pattern (standing-rule 3), don't drag in the old framework.

## The model the real code is forcing (preliminary — do not pre-mint)
The difference between "activity stream" and "storage-object update" is NOT the source —
it's the same cursor-delta primitive (`files_list_folder_continue`). The difference is
WHICH RECORDER consumes the delta and WHAT it writes. So:
- node-role: collector (emits delta), recorder (consumes delta, writes a destination)
- edge: wrangler (the coupling between them)
- fan-out: one delta → N recorders (dropbox already shows tensor + fact legs)
- feedback: a recorder-leg whose output re-enters a collector (re-collect changed file → Objects update)
- webhook-vs-polling: edge DELIVERY STRATEGY, not a topology difference (Direct/Batch/Queued axis)
This is what the providers reveal. Hold it as observation; let the design extract it.
