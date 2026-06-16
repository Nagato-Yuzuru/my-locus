---
title: "我早说过 ☝️🤓"
description: "对新闻、商业、技术的判断，发布即盖时间戳——事后照实打分，错的也认。"
---

{{< told-you-stats >}}

我对新闻、商业决策、技术方向的公开判断。每一条在发布当下就盖上密码学时间戳，事后无法偷偷改时间——并且事后照实打分，错的也照记。

## 如何验证 {#how-to-verify}

每条判断都被冻结进 `claim.txt`，并用 freeTSA.org 的 RFC 3161 时间戳（`proof.tsr`）封存。要验证某条判断在其声称的时间确实存在且未改动，下载该条的 `claim.txt` 与 `proof.tsr` 后运行：

```bash
openssl ts -verify -data claim.txt -in proof.tsr \
  -CAfile freetsa-cacert.pem -untrusted freetsa-tsa.crt
```

CA 链：[`freetsa-cacert.pem`](/tsa/freetsa-cacert.pem) · [`freetsa-tsa.crt`](/tsa/freetsa-tsa.crt)。
