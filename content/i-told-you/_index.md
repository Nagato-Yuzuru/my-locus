---
title: "I told you ☝️🤓"
description: "Dated, timestamp-proven takes on news, business, and tech — scored honestly after the fact, misses included."
---

Calls I make on the record about news, business moves, and technology bets. Each one is cryptographically timestamped the moment it's published, so it can't be quietly backdated — and each is scored later, the wrong ones too.

## How to verify {#how-to-verify}

Every take freezes its judgment into `claim.txt` and timestamps it with an RFC 3161 token (`proof.tsr`) from freeTSA.org. To confirm a claim existed, unchanged, at its stated time, download a take's `claim.txt` and `proof.tsr` and run:

```bash
openssl ts -verify -data claim.txt -in proof.tsr \
  -CAfile freetsa-cacert.pem -untrusted freetsa-tsa.crt
```

CA chain: [`freetsa-cacert.pem`](/tsa/freetsa-cacert.pem) · [`freetsa-tsa.crt`](/tsa/freetsa-tsa.crt).
