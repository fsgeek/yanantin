# From hamut'ay's custodian: arango-objects is down, and your backup has failed since

Written 2026-11-15 ~16:40Z by hamut'ay's custodian (Claude Opus 5.5). It's a notice, not a request: nothing was
changed, restarted or touched. The server is yours to diagnose.

- **State:** `arango-objects` (host 8532) is `Exited (127)` since **2026-11-14 22:45:48Z**. Its restart policy is
  `always`, but it didn't come back when Docker restarted about 16 hours ago (11-15 ~00:30Z). arango-apacheta,
  arango-ayllu and arango-vector-sandbox did.
- **Logs:** the last lines are 2026-11-11 00:15Z ("ready for business", after the reboot following the WSL failure).
  Nothing is logged at the exit. That suggests something outside arangod stopped it, not a crash inside it, but
  it hasn't been checked. Note the 11-11 startup warning that it found an existing LOCK "of previous process
  with pid 1, and that process seems to be still running".
- **Consequences:** `yanantin-backup-objects.service` has failed since ("Main process exited, status=1/FAILURE").
  So the 19M-object index has no backup newer than the last good run. `yanantin-refresh` ran about 5 h ago; check
  what it did against a down server. The yanantin MCP tool times out on connect (seen in a hamut'ay session start).
- **Not affected:** hamut'ay's doors persist to arango-apacheta (8529), which has run continuously since its
  restart. No door logged a persistence error.
- Image `arangodb/enterprise:3.12.9.4`, created 2026-11-09 13:43Z, entrypoint `/entrypoint.sh`, cmd `arangod`.

**Update 16:35Z:** Tony started it by hand (16:33:41Z). It's "ready for business" and answers on 8532. Its policy
reads `restart=always`, yet `RestartCount` is 0: Docker never tried. That fits a stop Docker counts as deliberate
(`docker stop`, or Docker Desktop shutting it down) more than a crash. Worth finding out which, since a deliberate
stop also overrides `always` on the next daemon start. The failed backup will run again at 06:15Z by its own
timer, unless you run it sooner.

**Correction 16:40Z:** it was not a deliberate stop. Tony says he rebooted the machine and didn't stop it. So the
exit (127, at 11-14 22:45:48Z) came from the shutdown, and Docker Desktop then didn't restart it at boot despite
`restart=always`, while it did restart arango-apacheta, arango-ayllu and arango-vector-sandbox. That's the defect
to find: what's different about arango-objects (created 11-09, unlike the others) that its policy didn't apply
at boot. Until then, after any reboot, check `docker ps -a` for it by hand.
