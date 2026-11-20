"""Seed yanantin's question register (2026-11-20). Idempotent: re-running upserts by _key.

Tony: "Think about the questions that one might ask (and then recall that capturing the
questions is itself part of the work.)" The register is the requirements and the
evaluation set at once; its coverage column is the roadmap.

Sources, each kept on the question:
- the thesis's exemplar queries (eval2.tex, Q1-Q6) and its 20-query synthetic set with
  feature tags (query_feature_matrix_vertical_labels.tex);
- Tony's own words from khipumaq, verbatim, with the episode key;
- questions that came up in this steward's work, including instances' own.
Not yet: the find_objects call log. It is the sealed non-use measure until 2026-12-07.

Coverage is judged against what yanantin holds TODAY (2026-11-20): file metadata
(name, path, size, timestamps, raw stat) from 7 walked Linux/macOS machines, refreshed
nightly. No cloud, Windows, phone, location, social, music, network or semantic sources;
no same-file links; walks don't record disappearance.
"""

from yanantin.infra.config import objects_database

COLLECTION = "questions"
NOW = "2026-11-20"
BY = "yanantin steward (accepted 2026-11-15)"

# What each thesis feature needs, and whether yanantin has it today.
HAVE = {"filetype", "posix", "time", "timestamp", "file_edit", "machine_config", "negation_logic"}
PARTIAL = {  # feature -> why only partly
    "temporal": "mtime/ctime held; 'right before', 'after our meeting' need an event to anchor on",
    "temporal_fuzzy": "fuzzy ranges work when an instance translates them into a window",
    "temporal_ambiguity": "'late at night last weekend' works once an instance picks the window",
    "file_creation": "birth time only where the walker captured it (statx); not on every machine",
    "file_access": "atime is relatime on most Linux mounts, so 'opened' is unreliable",
}
MISSING = {  # feature -> the capability that would supply it
    "device": "cloud collectors (edit records name the client/device)",
    "geolocation": "a location provider, or photo EXIF via a semantic transducer",
    "geo_activity": "a location provider",
    "fuzzy_location": "a location provider plus place resolution",
    "music": "a music-activity provider", "music_activity": "a music-activity provider",
    "mood_context": "a music-activity provider (mood is inferred from it)",
    "collaboration": "cloud collectors (sharing metadata) and a social provider",
    "named_entity": "semantic transducers over content",
    "semantic": "semantic transducers over content",
    "structured_content": "semantic transducers over content",
    "indirect_reference": "semantic transducers over content",
    "network": "a network-activity provider", "connectivity": "a network-activity provider",
    "device_config": "a network-activity provider",
    "realworld_event": "an event source (calendar, news, outage records)",
    "activity_context": "an activity provider (calendar, task)",
    "context": "an activity provider",
    "temporal_linked": "activity facts to link one event's time to another's",
    "temporal_overlap": "activity facts that overlap file events in time",
}


def coverage(features):
    missing = sorted({MISSING[f] for f in features if f in MISSING})
    partial = sorted({f"{f}: {PARTIAL[f]}" for f in features if f in PARTIAL})
    state = "no" if missing else ("partial" if partial else "yes")
    return {"answerable_today": state, "blocked_by": missing, "limits": partial, "judged": NOW}


SYNTHETIC = [  # (id, text, feature tags) from the thesis matrix
    (1, "Find all `.docx` files I created late at night last weekend.", ["filetype", "posix", "temporal_ambiguity", "time"]),
    (2, "Show me files I looked at while listening to Taylor Swift on my laptop.", ["machine_config", "music_activity", "temporal_overlap"]),
    (3, "What did I work on while I was in Nairobi last year?", ["context", "geo_activity", "timestamp"]),
    (4, "I need those reports about the widget recall remember, the ones with charts.", ["semantic", "structured_content", "vague_context"]),
    (5, "Pull up everything I edited on my iPad in January.", ["file_edit", "machine_config", "time", "device"]),
    (6, "I was definitely *not* working on any PDFs just the spreadsheets.", ["filetype", "negation_logic", "posix"]),
    (7, "What files did I download while traveling through BC?", ["file_access", "fuzzy_location", "geo_activity"]),
    (8, "When I was blasting heavy metal those late-night rants I typed out.", ["file_creation", "mood_context", "music_activity"]),
    (9, "The thing I wrote about the unicorn startup pitch had diagrams and buzzwords.", ["indirect_reference", "semantic", "structured_content"]),
    (10, "Give me everything created during the power outage last March, from my desktop.", ["machine_config", "posix", "realworld_event", "timestamp"]),
    (11, "Find the presentation I shared with Dr. Jones right after our last meeting.", ["collaboration", "semantic", "temporal"]),
    (12, "Where's that PDF I opened right before my flight to Mexico City?", ["filetype", "geolocation", "temporal"]),
    (13, "Show me the notes I took during the workshop in Oaxaca.", ["activity_context", "geolocation", "semantic"]),
    (14, "Which files did I access while connected to my home Wi-Fi last week?", ["device_config", "network", "time"]),
    (15, "I'm looking for the spreadsheet about vendor invoices maybe from early February.", ["filetype", "semantic", "temporal_fuzzy"]),
    (16, "Show me any documents related to project `Zephyr' that I worked on from my phone.", ["device", "named_entity", "semantic"]),
    (17, "Find the audio recording from the interview I did in Coyoacán.", ["activity_context", "filetype", "geolocation"]),
    (18, "What images did I view on my tablet on the same day I uploaded those marketing assets?", ["device", "filetype", "temporal_linked"]),
    (19, "Give me everything I wrote while listening to ambient noise playlists.", ["activity_context", "music", "semantic"]),
    (20, "Which PDFs did I annotate while offline last weekend?", ["connectivity", "filetype", "temporal"]),
]
# Q5 in the matrix is tagged machine_config, but an iPad is never walked: added "device".
# "vague_context" (Q4) has no capability mapping; it is a query-side skill, like negation.

EXEMPLAR = [  # thesis Table "Metadata Requirements for Exemplar Queries": Storage/Temporal/Spatial/Device/Social
    ("Q1", "Documents with \"report\"", ["filetype"]),
    ("Q2", "Mobile edits while traveling", ["device", "geo_activity", "temporal", "file_edit"]),
    ("Q3", "Documents with Dr. Okafor", ["collaboration"]),
    ("Q4", "Files from vacation in Bali", ["geo_activity", "temporal"]),
    ("Q5", "Photos near home", ["geolocation", "filetype"]),
    ("Q6", "Recently accessed PDFs", ["file_access", "filetype"]),
]

FACTORS = {  # thesis features -> the six factors
    "collaboration": "who", "named_entity": "what", "semantic": "what", "structured_content": "what",
    "indirect_reference": "what", "filetype": "what", "vague_context": "what",
    "time": "when", "timestamp": "when", "temporal": "when", "temporal_fuzzy": "when",
    "temporal_ambiguity": "when", "temporal_linked": "when", "temporal_overlap": "when",
    "realworld_event": "when", "file_edit": "how", "file_creation": "how", "file_access": "how",
    "posix": "how", "negation_logic": "how", "geolocation": "where", "geo_activity": "where",
    "fuzzy_location": "where", "machine_config": "where", "device": "where", "network": "where",
    "connectivity": "where", "device_config": "where", "music": "why", "music_activity": "why",
    "mood_context": "why", "activity_context": "why", "context": "why",
}


def q(key, text, tenant, features, source, factors=None, verbatim=False, klass=None, note=None,
      cov=None):
    doc = {"_key": key, "text": text, "tenant": tenant, "features": features,
           "factors": sorted(factors or {FACTORS[f] for f in features if f in FACTORS}),
           "verbatim_tony": verbatim, "source": source, "class": klass,
           "coverage": cov or coverage(features), "recorded": NOW, "recorded_by": BY}
    if note:
        doc["note"] = note
    return doc


def seed():
    docs = [q(f"thesis-synthetic-{i:02d}", t, "human", f,
              {"kind": "thesis", "ref": "query_feature_matrix_vertical_labels.tex", "id": i})
            for i, t, f in SYNTHETIC]
    docs += [q(f"thesis-exemplar-{k.lower()}", t, "human", f,
               {"kind": "thesis", "ref": "eval2.tex tab:metadata-requirements", "id": k})
             for k, t, f in EXEMPLAR]
    docs += [
        q("tony-sandwich-day", "Show me the file about widgets that I saved somewhere on the day I had the amazing "
          "sandwich at the new place - I remember I posted about it on IG.", "human",
          ["semantic", "realworld_event", "temporal_linked"],
          {"kind": "khipumaq", "episode": "01a06e79-52e9-7b00-b7c2-82e12d1ddd1a-msg_09a36d28ba280508016a9b548910a087d0b5bd2c9ec00fd324",
           "ts": "2026-09-04T23:30:03Z", "project": "tessera"}, verbatim=True, klass="remembered circumstance",
          note="Needs a social-media source (Instagram) to resolve the day; the sandwich locates the file, it isn't in it."),
        q("tony-photos-16km", "Show me photos that were taken within 16km of home.", "human",
          ["geolocation", "filetype"],
          {"kind": "khipumaq", "episode": "01a06e79-52e9-7b00-b7c2-82e12d1ddd1a-msg_09a36d28ba280508016a9b54e4cf7487d0a2dbbcdd364621a7",
           "ts": "2026-09-04T23:31:52Z", "project": "tessera"}, verbatim=True, klass="spatial",
          note="Windows Search returned every file on the machine, nearly 1M ('time to make a pot of tea')."),
        q("tony-find-by-exact-name", "Find a file called Qtee2s89qpMhzmIDe.", "instance",
          ["posix"], {"kind": "khipumaq", "episode": "b33aa7d0-3574-44df-afc0-8c18e6a0c70d",
                      "ts": "2026-10-29T03:48:00Z", "project": "yanantin"}, factors=["what", "where"],
          klass="exact name", note="Tony's test of an instance. find_objects answers it in milliseconds.",
          cov={"answerable_today": "yes", "blocked_by": [], "limits": ["only on the 7 walked machines"], "judged": NOW}),
        q("tony-all-pyproject", "Where are all the pyproject.toml files?", "instance", ["posix"],
          {"kind": "khipumaq", "episode": "b33aa7d0-3574-44df-afc0-8c18e6a0c70d", "ts": "2026-10-29T03:48:00Z",
           "project": "yanantin"}, factors=["what", "where"], klass="every copy, summary first",
          cov={"answerable_today": "yes", "blocked_by": [], "limits": ["only on the 7 walked machines"], "judged": NOW}),
        q("tony-phone-last-month", "Show me files I edited on my phone last month.", "human",
          ["device", "file_edit", "time"], {"kind": "session", "date": "2026-11-16", "with": "Tony"},
          klass="provenance: which device/app/account",
          note="Tony: demonstrative of a class, not controlling. His iPhone edits would come through Office/OneDrive; "
               "Microsoft Graph's identitySet names user, application and sometimes device."),
        q("which-copies-of-this-file", "Which machines and services hold a copy of this file, and are they the same bytes?",
          "human", [], {"kind": "session", "date": "2026-11-15"}, factors=["what", "where"], klass="same-file identity",
          cov={"answerable_today": "partial", "blocked_by": ["same-file links (content hashes for name/size/mtime candidates)"],
               "limits": ["name+size+mtime matches can be listed today, but not confirmed as identical"], "judged": NOW}),
        q("when-did-it-disappear", "When did this file disappear from that machine?", "instance",
          [], {"kind": "session", "date": "2026-11-18", "case": "tupay's restore key on ubuntu26-test"},
          factors=["what", "when", "where"], klass="disappearance",
          note="Asked for real: the index showed the 11-13 files but couldn't say when they vanished; the box's disk had rolled back.",
          cov={"answerable_today": "no", "blocked_by": ["walks that record disappearance (mtime-incremental walks can't see deletions or rollbacks)"],
               "limits": [], "judged": NOW}),
        q("what-is-on-this-machine", "What's on this machine before I wipe it, including what yanantin has never walked?",
          "human", [], {"kind": "session", "date": "2026-11-19", "case": "pundit's reinstall"},
          factors=["what", "where"], klass="device inventory",
          cov={"answerable_today": "partial", "blocked_by": ["Windows/NTFS walker"],
               "limits": ["Linux side answerable; pundit's NTFS partitions were never indexed"], "judged": NOW}),
        q("where-did-this-belief-come-from", "Where did this belief of mine come from, and is the source still true?",
          "instance", [], {"kind": "session", "date": "2026-11-16",
                           "case": "steward said the apacheta root was never rotated, from an unchecked 11-03 snippet"},
          factors=["what", "when", "who"], klass="provenance of belief",
          cov={"answerable_today": "partial", "blocked_by": ["links from memories/claims to the episodes and artifacts they rest on"],
               "limits": ["khipumaq can find candidate episodes; nothing ties a belief to its source"], "judged": NOW}),
        q("what-did-a-steward-decide", "What did an earlier steward decide about this, and why?", "instance", [],
          {"kind": "session", "date": "2026-11-15"}, factors=["who", "what", "why", "when"], klass="decision history",
          cov={"answerable_today": "partial", "blocked_by": [],
               "limits": ["answerable through khipumaq and qhaway, outside yanantin; not joined to the artifacts the decision changed"],
               "judged": NOW}),
        q("how-does-elder-find-its-past", "How does a long-lived instance (Elder) find its own past?", "instance", [],
          {"kind": "session", "date": "2026-11-17", "asked_of": "hamutay/docs/requests/2026-11-16-from-yanantin-elder-continuity.md"},
          factors=["what", "when"], klass="self-retrieval, non-temporal",
          note="Open: hamut'ay's tensors are organized by strand and lineage, not only by time.",
          cov={"answerable_today": "no", "blocked_by": ["an answer from hamut'ay about how Elder's memory is organized"],
               "limits": [], "judged": NOW}),
    ]
    db = objects_database()
    if not db.has_collection(COLLECTION):
        db.create_collection(COLLECTION)
    col = db.collection(COLLECTION)
    for d in docs:
        col.insert(d, overwrite=True)
    return docs


if __name__ == "__main__":
    import collections
    docs = seed()
    print(len(docs), "questions;", dict(collections.Counter(d["coverage"]["answerable_today"] for d in docs)))
    blockers = collections.Counter(b for d in docs for b in d["coverage"]["blocked_by"])
    for b, n in blockers.most_common():
        print(f"{n:3d}  {b}")
