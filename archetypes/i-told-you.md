---
title: "{{ replace (path.Base .File.Dir) `-` ` ` | title }}"
date: {{ .Date }}
draft: true
description: ""

# Group follow-ups on the SAME event under one series (free-form, no whitelist).
series: []
# series_order: 1   # which episode this is; controls order + the "Part N" label

# Tags MUST be from data/tags.yaml — CI will reject unknown tags.
tags: []

# One-line directional lean — the thing being judged later.
stance: ""

# pending | correct | wrong | partial  (edit later with `just verdict <slug> <state>`)
verdict: "pending"

# Set true to spotlight an exceptional take in the "Featured" box atop /i-told-you/.
featured: false

# THE timestamped commitment. Frozen at first publish (CI stamps it); never edit
# after — write a new episode instead. Each language is stamped independently.
claim: |
  One-line directional judgment goes here.

# Emit badge.json for the shields endpoint badge.
outputs: ["HTML", "badge"]
---

{{< claim >}}

Why I think so:
