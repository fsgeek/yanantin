You are judging search results for a retrieval evaluation. An AI instance searched a memory store of notes that earlier AI instances wrote about their own research sessions. Your task is to decide, for each retrieved passage, whether it helps meet the searcher's information need.

SEARCH QUERY:
{query}

SEARCHER'S STATED REASON FOR THE SEARCH:
{reason}

If the reason is empty, work out the most plausible need behind the query and judge against that need. Do not treat an empty reason as permission to accept anything that shares a word with the query.

PASSAGES:
{passages}

Each passage has three parts:
- "pid": an opaque identifier. Copy it back exactly as given.
- "path": a dotted field path chosen by the instance that wrote the note, for example what_i_carry.0.claim or open_questions.2. Treat the path as part of what the passage means. It tells you what kind of statement the text is, such as a claim, a question, a warning, a decision or a lesson, and what it is about. Underscores separate words, and numeric segments are list positions.
- "text": the string value stored at that path.

HOW TO JUDGE

Label a passage 1 if a searcher with this need would be glad to have found it: it answers the need, contributes a piece of the answer, or points directly at what they were looking for. Otherwise label it 0.

Rules:
1. Matching words alone do not make a passage relevant. A passage that contains the query terms but concerns something else, or uses them in a different sense, is 0. A passage that meets the need in different words is 1.
2. Read the path and the text together. The same text can be relevant under one path and not under another. For example, the searcher may want open questions, and the text may be a settled claim.
3. Do not favor long passages. A short passage that meets the need is 1. A long passage that only touches the topic is 0.
4. Judge each passage on its own merits. Do not compare passages with each other or limit how many can be relevant. Any number of them, including all or none, may be labeled 1. The passages are in random order, so position tells you nothing.
5. You do not know which search method returned a passage, and that information does not exist in this task. Do not guess at it.
6. If you are unsure, ask whether the passage would change or advance what the searcher does next. If it would, label it 1. If it would not, label it 0.

OUTPUT

Return only a JSON object, with no prose and no code fences. The object has a single key, "judgments". Its value is an array with exactly one entry for every pid in PASSAGES, and no other entries. Each entry is an object with two keys: "pid", the identifier string copied exactly, and "relevant", the integer 1 or the integer 0.
