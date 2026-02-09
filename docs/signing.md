# Code Signing

## Principle

Every commit carries provenance. AI-authored commits are signed with
an AI key, distinct from human signing keys. The git log becomes an
epistemic observability layer — you can see who authored what,
verifiably.

## Setup

TODO: Generate GPG key pair for Yanantin AI identity. Steps:

1. Generate key: `gpg --gen-key` with identity like
   "Yanantin AI <yanantin-ai@project>"
2. Configure git to use the key for AI commits
3. Export public key for verification
4. Store private key accessible to Claude Code sessions

## Open Questions

- One key per project, or one key per AI model family?
- Should the key identity encode the model (e.g., "claude-opus-4-6")?
- Key rotation policy?
- How to handle collaborative commits (AI + human co-authored)?
  Possibly dual-signed, or signed by whichever party made the commit
  with co-authorship in the commit message (current practice).
