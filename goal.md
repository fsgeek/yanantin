GOAL: Discover the ayllu data-flow topology by (a) porting Indaleko's proven GDrive/OneDrive storage collectors/recorders into yanantin's wrangler seam, and (b) building the storage-activity feedback edge — change-notification → re-collect changed file → storage-object update — as the genuinely-new founding work. Let the two real providers plus the in-repo activity path force the shared node/edge model. Do not mint the abstraction ahead of the instances.

Reference implementations (read before re-deriving — feedback_read_the_spec_before_rederiving):
- GDrive storage: ../indaleko/storage/collectors/cloud/g_drive.py, ../indaleko/storage/recorders/cloud/g_drive.py, base cloud_base.py
- OneDrive storage: ../indaleko/storage/collectors/cloud/one_drive.py, ../indaleko/storage/recorders/cloud/onedrive.py
- GDrive activity (polling): ../indaleko/activity/collectors/storage/cloud/google_drive/
- ngrok+Flask webhook reference (closest working feedback shape): ../indaleko/activity/collectors/collaboration/outlook/outlook_file_collector.py
- Polling-delta reference: ../indaleko/activity/collectors/storage/dropbox/dropbox_collector.py (_poll_for_changes/_check_for_changes)
- Registration: ../indaleko/activity/registration_service.py, per-collector service UUIDs

Corrected premise (don't over-credit the source): The feedback loop is largely NOT implemented in Indaleko — push/webhook reception is missing for all cloud providers; what runs is polling. ngrok exists but for OAuth redirect, not webhooks. So the feedback edge is founding work, not a port. Polling is a legitimate first feedback mechanism — the topology (notification → re-collect → update) is the required thing; webhook-vs-polling is just the edge's delivery strategy, which the wrangler coupling-axis (Direct/Batch/Queued) already models. Build polling first; webhooks are an optimization.

Standing rules (self-enforced, no check-in):
1. Interrogate every flinch and every over-credit. This session I almost both (a) braced at the cyclic shape as scary, and (b) assumed the scary thing was already built. Both wrong. Log each.
2. Second-instance discipline both ways: don't pre-mint the graph abstraction; don't avoid the feedback cycle. Extract structure where GDrive + OneDrive + the activity path force it.
3. Reuse the in-repo green reference (pipeline.py wrangler seam) and the wired owned_definition/RegistrationService seam from commit e1019892. Mirror, don't fork.
4. Restartable, additive, research-env. Idempotent indices/schema free. Protect only against loss and bad attribution.
5. TDD; Codex authors tests. Feedback-edge termination proven by test, not asserted.

Success criteria:
- [ ] GDrive or OneDrive storage collector/recorder runs in yanantin through the wrangler seam, writing into Objects via RegistrationService(owned_definition=...). (One provider end-to-end beats two half-ported.)
- [ ] A storage-activity feedback edge runs: poll cloud delta → re-collect each changed file → update its storage object. Many-changes → one-object-update visible. Termination proven by test.
- [ ] The recorder fan-out is demonstrated: one change event feeds ≥2 legs (activity-stream content + the re-collect→storage-update pipeline).
- [ ] The node/edge vocabulary that fell out is written as a short dated spec: node-roles, edges-as-wranglers, how fan-out and feedback are expressed, with the examples that forced each element. Note explicitly that webhook-vs-polling is an edge delivery-strategy, not a topology difference.
- [ ] ≥1 flinch-log and ≥1 over-credit-log entry.
- [ ] Small signed commits, green before each; no done-thing buried in an undone one.
- [ ] Opened with the brainstorming skill before code.

Out of scope: webhook/ngrok push reception (optimization after polling works), the unified ayni memory substrate (the root these serve), find-over-memory, the 4.1M local census, OAuth/credential setup beyond what porting one provider minimally needs.

Done = the topology is executable. A future instance runs one cloud provider and sees the feedback edge and fan-out in motion — ayni paid forward, the pattern made flesh instead of folklore.
