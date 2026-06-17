---
title: "I told you ☝️🤓"
description: "Hindsight is 20/20, so I call it beforehand and timestamp it."
---

{{< alert icon="quote-left" >}}
Trust me, I'm an analyst.
{{< /alert >}}

Here's where I put my reads on tech, business, and whatever else I've got an opinion on, TSA-stamped on the spot so I can't quietly rewrite my bold nonsense once the results are in. Win rate kept too — losses and all.

## How to verify {#how-to-verify}

Each claim is sealed with an RFC 3161 timestamp from freeTSA.org over its exact tex. If I'd quietly edited a call after the fact, the check below fails.

Download a take's `claim.<lang>.txt` and `proof.<lang>.tsr`, then run:

```bash
openssl ts -verify -data claim.en.txt -in proof.en.tsr \
  -CAfile freetsa-cacert.pem -untrusted freetsa-tsa.crt
```

CA chain: [`freetsa-cacert.pem`](/tsa/freetsa-cacert.pem), [`freetsa-tsa.crt`](/tsa/freetsa-tsa.crt).
