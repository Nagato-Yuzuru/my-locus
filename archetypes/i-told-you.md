---
title: "{{ replace (path.Base .File.Dir) `-` ` ` | title }}"
date: {{ .Date }}
draft: true
description: ""

# Group follow-ups on the SAME event under one series (free-form, no whitelist).
series: []

# Tags MUST be from data/tags.yaml — CI will reject unknown tags.
tags: []

# One-line directional lean — the thing being judged later.
stance: ""

# pending | correct | wrong | partial  (edit later with `just verdict <slug> <state>`)
verdict: "pending"

# Language whose claim.txt is the timestamped record (en => index.md, zh-cn => index.zh-cn.md).
claim_lang: "en"

# Emit badge.json for the shields endpoint badge.
outputs: ["HTML", "badge"]
---

{{< claim >}}
<!-- One-line directional judgment. Frozen on publish — never edit after.
     New developments on this event go in a NEW episode (same series), not here. -->
{{< /claim >}}

Why I think so:
