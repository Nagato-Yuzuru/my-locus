---
title: "{{ if eq .File.ContentBaseName `index` }}{{ replace (path.Base .File.Dir) `-` ` ` | title }}{{ else }}{{ replace .File.ContentBaseName `-` ` ` | title }}{{ end }}"
date: {{ .Date }}
lastmod: {{ .Date }}
draft: true
description: ""

# Tags MUST be from data/tags.yaml — CI will reject unknown tags.
tags: []

# Set to false to skip auto-translation for this post.
translate: true
---
