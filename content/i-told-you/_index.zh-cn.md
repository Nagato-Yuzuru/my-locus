---
title: "我早说过 ☝️🤓"
description: "用TSA盖章的事前臭皮匠"
---

{{< alert icon="quote-left" >}}
专业解说要勇于下判断
{{< /alert >}}

我会把自己对某些新闻/事件/技术/商业等等事情的判断放在这里，并且用TSA盖章来保证大胆的口胡没有被篡改。并且统计胜率。

## 如何验证 {#how-to-verify}

每条判断都用 freeTSA.org 的 RFC 3161 时间戳封在它的原文字节上，我要是事后偷偷改过，下面这条命令就会失败。

下载某条的 `claim.<lang>.txt` 和 `proof.<lang>.tsr`，然后跑：

```bash
openssl ts -verify -data claim.en.txt -in proof.en.tsr \
  -CAfile freetsa-cacert.pem -untrusted freetsa-tsa.crt
```

CA 链：[`freetsa-cacert.pem`](/tsa/freetsa-cacert.pem)、[`freetsa-tsa.crt`](/tsa/freetsa-tsa.crt)。
