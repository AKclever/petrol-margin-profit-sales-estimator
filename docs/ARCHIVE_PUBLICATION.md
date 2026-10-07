# Research archive publication

Source code, frozen specifications, results, source checks and supporting
evidence are versioned on the research branch. Local virtual environments,
package build artifacts, environment files and private-key files are excluded.

Raw `data/daily_prices/**/aaa_snapshot.html` captures are also excluded because
the public pages embed a third-party browser API key. Their immutable local
bytes have not been redacted or rewritten. Normalized retail observations and
original SHA-256 values remain versioned, but the GitHub checkout alone cannot
reproduce the AAA HTML parsing. The raw-source parser test skips when that
local evidence is absent. Request the original local evidence for an audit;
do not pretend a new webpage download is the same historical snapshot.

The repository includes Cloud Run deployment instructions, not proof of a
deployed scheduler. Pushing this branch does not deploy infrastructure, enable
billing, or schedule automatic collection.
