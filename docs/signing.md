# Code Signing

## Principle

Every commit carries provenance. AI-authored commits are signed with
an AI key, distinct from human signing keys. The git log becomes an
epistemic observability layer — you can see who authored what,
verifiably.

## Current Keys

### Human (Tony Mason)
- **Identity:** Tony Mason <fsgeek@cs.ubc.ca>
- **Key ID:** `5F5BF6BAEC2541D2`
- **Fingerprint:** `72FF6DD094CE835A5089BB9D5F5BF6BAEC2541D2`
- **Configured:** Global git config

### AI (Claude Opus)
- **Identity:** Yanantin AI (Claude Opus) <yanantin@wamson.com>
- **Key ID:** `D0CAB9659C950893`
- **Fingerprint:** `1E416B1FB63AF88179EE0F38D0CAB9659C950893`
- **Expires:** 2027-02-09
- **No passphrase.** Security boundary is machine/user access, not
  key passphrase. Honest about what it is — a passphrase stored for
  non-interactive access would be theater.
- **Configured:** Per-command git overrides (not repo-level, to avoid
  stepping on human commits).

## How Signing Works

Tony's global git config handles his identity and signing key.
AI commits use per-command overrides:

```bash
git -c user.name="Yanantin AI (Claude Opus)" \
    -c user.email="yanantin@wamson.com" \
    -c user.signingkey=1E416B1FB63AF88179EE0F38D0CAB9659C950893 \
    commit -S -m "message"
```

GitHub verification requires:
1. Register yanantin@wamson.com as email on GitHub account
2. Upload AI public key to GitHub

Export public key for GitHub:
```bash
gpg --armor --export yanantin@wamson.com
```

## Decisions Made

- **One key per project**, with model family encoded in the UID string.
  The key says "this project trusts this AI to commit." The UID says
  which AI. If a different model family operates here, it gets its own key.
- **Model identity in UID:** Yes. `Yanantin AI (Claude Opus)` distinguishes
  from a hypothetical `Yanantin AI (Claude Sonnet)` or future models.
- **Key rotation:** Annual (1-year expiry). Rotate on model family change.
- **Collaborative commits:** Signed by whichever party makes the commit,
  with `Co-Authored-By` in the commit message for the other party.

## OpenTimestamps

In progress (Tony). Adds signed timestamps to commits for
tamper-resistant temporal provenance. Not tamper-proof, but raises
the cost of falsification.
