---
title: "把基础设施能力变成产品: 用 CRD 让领域专家自助上线"
date: 2026-05-25T12:16:11+08:00
draft: true
description: "从每域名一证书到 DomainRoute——我们如何用一个 CRD 屏蔽 k8s 与非 k8s 后端的差异，让领域专家在网页上自助上线，以及一路踩过的坑。"

# Tags MUST be from data/tags.yaml — CI will reject unknown tags.
tags: ["devops", "cloud-native"]

# Optional: group post into a named series (free-form, no whitelist).
# Example: series: ["Tokio Deep Dive"]
# series: []

# Set to false to skip auto-translation for this post.
translate: false
---

## 背景与约束：为什么非做不可

我所在的公司是一个气象数据和算法驱动的能源期货交易领域的垂直SaaS和平台，业务和需求高度依赖领域专家的交易与市场知识。Agentic Coding的发展给我们带来了巨大的生产力提升。现在领域专家和交易员可以根据自己的需求和痛点让AI进行快速的产品开发。

原本我们运营2-3个核心产品，随着生产力的迸发以极快的速度增长（题外话，我们老板搓了很多内部服务。有的确实很有用。但是大部分感觉更接近一个"界面更炫酷，并且可以直接在上面交互的Grafana"）。并且产品上线测试的速度也蹭蹭往上涨。

协作模式跟着变了。原来是按角色横切，dev、ops、产品各管一段。现在成了"谁有想法谁就自己做、自己发、自己维护"。理想情况下，至少在正式发布前，一个人能从"我想要个东西"一路闭环到上线。问题是老流程里域名、证书这些环节，根本扛不住这种玩法。还有一个痛苦的现实，领域专家（和部分算法团队）对k8s的使用相对"抗拒"。他们有相当数量的服务部署在云托管的虚拟机上。他们不想去学习这些让人头晕眼花的"老古董"，我们（或者任何心智正常的工程师）都不会想把网关/域名/证书这种东西扔给公司里任意一个人用的任意AI。

显而易见的，域名/网关等配置会成为产品闭环的阻碍。

## 一个新产品要上线

以前一个新产品上线，有专门的人( 虽然大多数时候是dev客串ops )进行部署、网关配置、域名绑定，改DNS等等。周期以月计算。现在不一样了。尤其是我亲眼看到以前不具有实际工程能力的人发现Agent可以在非常快的时间把他们的想法变成一个基本可用的产品。他们很多人都表现出了一种狂热甚至某种上瘾。如果你一星期晚上连着四五次被老板call起来让你帮他配置域名等等，你会打心底意识到这方法是不可持续的。

我们需要一个对大家都好的方法能让这些破事在我们的管理平台网页（我个人当然喜欢用yaml配置和cli。我的vim和shell锋利无比。但是大概率那些领域专家们和老板不会这么想）5分钟自助搞定。

## 网络拓扑：一张通配符撑起所有产品

在讨论这个 CRD 前，先具体介绍一下当前的网络架构。

{{< mermaid >}}
flowchart TB
dom["产品域名<br>CNAME 由 operator 建"]
dom -->|"lb=alb-out"| albout["alb-out<br>公网 ALB"]
dom -->|"lb=alb-in"| albin["alb-in<br>内网 ALB"]

    albout --> igw["istio-ingressgateway"]
    albin --> igw

    igw --> route["每域名一套 Gateway + VirtualService<br>operator 按 host 生成"]

    route --> ksvc["k8s Service<br>集群内后端"]
    route --> se["ServiceEntry<br>到集群外虚拟机"]

    cert["通配证书 *.example.com<br>自动签发 + 续期"] -. TLS 终止 .-> albout
    cert -. TLS 终止 .-> albin

{{< /mermaid >}}

形状很简单。两个 ALB，一个对公网（alb-out），一个对内网（alb-in）。后面是同一套 Istio IngressGateway，按 Host 分流到各个产品。一个产品域名走哪个 ALB，通过 CR 里的一个字段（`lb`）说了算。Operator 据此给这个域名建一条 CNAME，指向对应 ALB 的记录。

省事的关键在两处自动化。其一，新产品要 `newthing.example.com`，没有人需要手工碰 DNS。Operator 调 DNS 厂商的 API，自动建好那条指向 ALB 的 CNAME。其二，ALB 上挂着一张 `*.example.com` 的通配证书，新子域名的 TLS 被它直接覆盖，不用单独签。把需要流程化的事情通过Operator完成。

证书这块还有个容易看错的点要澄清：TLS 是在 ALB 上终止的，Istio 网关只管 HTTP 的 host 路由。所以"证书"这件事发生在云ALB，不在mesh里。还有个现实的小麻烦：我们的 DNS 和 LB 不在同一个云厂商，DNS-01 的验证打到 A 云的 DNS，签出来的证书得再推到 B 云的 LB 上，这条跨云链路得自己接通。在这之前我们是每个域名一张证书、手动传、偶尔忘了续期就半夜收到一个过期告警，甚至是被客户告知。

### 这套拓扑的代价

通配符省下来的便利是用几个新风险换的：

- 通配证书的爆炸半径。一张 `*.example.com` 的私钥泄露，等于整个后缀下所有产品一起沦陷。便利和爆炸半径是同一枚硬币的两面。
- 通配只覆盖一层。`*.example.com` 不匹配 `a.b.example.com`。需要多级子域名的产品得单独处理。
- CDN走单独的证书。不过CDN相关的网络配置变动频率很低。不纳入这套系统我认为是合适的。
- DNS-01 需要 DNS 的写权限。通配证书没法用 HTTP-01，只能走 DNS-01，这意味着签发流程手里攥着改 DNS 记录的 API token。又一个要小心看管的高权限凭据。
- 共享入口 == 共享命运。所有产品的流量挤同一套 IngressGateway，一个产品的配置错误或流量洪峰，理论上会波及邻居。收敛带来的运维简化，代价是把鸡蛋放进了同一个篮子，这个篮子的韧性（多副本、跨可用区、健康检查）必须单独下功夫。

## 统一抽象：一个 CR 屏蔽 k8s 与非 k8s 后端

这套东西的核心：`DomainRoute` CR。一个 DomainRoute 描述一个被完整托管的域名——DNS 记录、绑在 ALB 上的证书覆盖、对应的 Istio Gateway 和 VirtualService，以及可选的网关保护。领域专家在网页上填的那张表背后就是它（说服负责管理平台的同事加一个k8s sdk 依赖而不是再对 APIService 封装一个API服务是一个艰巨的任务。他们会觉得k8s内部是一个神秘莫测的黑箱而拒绝引入这个依赖。我做到了）。

spec 大概长这样：

<details>
<summary>展开 DomainRoute 的 Go 类型定义</summary>

```go
// LBSelector 决定流量走哪个 ALB：公网还是内网。
// +kubebuilder:validation:Enum=alb-out;alb-in
type LBSelector string

const (
	LBALBOut LBSelector = "alb-out" // 公网 ALB
	LBALBIn  LBSelector = "alb-in"  // 内网 ALB
)

// ServiceBackend：集群内的 Kubernetes Service。
type ServiceBackend struct {
	// +kubebuilder:validation:Required
	Name string `json:"name"`
	// 跨命名空间时指定；留空则用 DomainRoute 自己的命名空间。
	// +optional
	Namespace string `json:"namespace,omitempty"`
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=65535
	Port int32 `json:"port"`
}

// ExternalBackend：集群外的虚拟机端点。operator 用一条 Istio ServiceEntry
// 把它注册成网格里可路由的目标。只接受 IPv4，不做域名解析。
type ExternalBackend struct {
	// +kubebuilder:validation:Pattern=`<IPv4 点分十进制>`
	IP string `json:"ip"`
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=65535
	Port int32 `json:"port"`
	// +kubebuilder:validation:Enum=HTTP;HTTPS;TCP
	// +kubebuilder:default=HTTP
	Protocol string `json:"protocol,omitempty"`
}

// Backend 是一个判别联合：service 与 external 至多设一个。
// +kubebuilder:validation:XValidation:rule="!(has(self.service) && has(self.external))",message="at most one of service or external may be set"
type Backend struct {
	// +optional
	Service *ServiceBackend `json:"service,omitempty"`
	// +optional
	External *ExternalBackend `json:"external,omitempty"`
}

// RoutingMode：VirtualService 归谁管。
// Managed（默认）= operator 生成；External = 应用团队自己写。
// +kubebuilder:validation:Enum=Managed;External
type RoutingMode string

// ProtectionSpec：可选的网关鉴权。
type ProtectionSpec struct {
	// 预先在 mesh 里注册的外部鉴权 provider 名；未知则 fail closed。
	// +kubebuilder:validation:Required
	Provider string `json:"provider"`
	// 调用方身份，全局唯一；重复则 ProtectionReady=False / AppIDConflict。
	// +kubebuilder:validation:Required
	AppID string `json:"appId"`
    // 控制具体的保护方式和放行url
	// +optional
	Rules []ProtectionRule `json:"rules,omitempty"`
}

// DomainRouteSpec：一个 DomainRoute 描述一个被完整托管的域名。
//
//   - routing.mode=Managed（默认）：backend.service / backend.external 必须恰好设一个。
//   - routing.mode=External：backend 必须留空，VirtualService 由应用团队拥有。
//
// +kubebuilder:validation:XValidation:rule="(has(self.routing) && self.routing.mode == 'External') ? (!has(self.backend) || (!has(self.backend.service) && !has(self.backend.external))) : (has(self.backend) && (has(self.backend.service) || has(self.backend.external)))",message="..."
type DomainRouteSpec struct {
	// 例如 api.example.com
	// +kubebuilder:validation:Required
	Domain string `json:"domain"`

	// +kubebuilder:validation:Required
	LB LBSelector `json:"lb"`

	// +optional
	Routing RoutingSpec `json:"routing,omitempty"`

	// Managed 模式下指定后端；External 模式下必须为空。
	// +optional
	Backend Backend `json:"backend,omitempty"`

	// +kubebuilder:validation:Required
	DNS DNSSpec `json:"dns"`

	// 不设则网关直接放行（无鉴权）。
	// +optional
	Protection *ProtectionSpec `json:"protection,omitempty"`
}
```

</details>

挑几个我觉得设计上最关键的点说。

**一个 `backend` 字段是对不愿意上 k8s 的妥协。**（你懂的，越说不动的越在食物链顶层）（遗憾的是我没能说服他在 k8s 上部署，发布原语+自愈等功能很难在外部复制）。这是整套东西存在的理由。后端要么是集群内的一个 `Service`，要么是集群外的一台虚拟机（`external` 里就是 IP、端口、协议）。差异由 operator 吃掉。是 Service，就直接指向集群里那个 Service；是 external，operator 就生成一条 Istio `ServiceEntry`，把那台不归 k8s 管的虚拟机注册成网格里一个可路由的目标。对填表的人来说，"我的东西跑在 k8s 里"和"我的东西是台虚拟机"，填的是同一张表的同一个位置，拿到的是同样的 DNS、证书、网关、可选保护。开头说的"屏蔽 k8s 与非 k8s 的差异"，落地就是这一个判别联合。

**Managed 是默认，External 是逃生舱。** 大多数人只想要"把这个域名指到我的服务上"，那 operator 连 VirtualService 都替他生成，他这辈子不用知道 Istio 是什么。但总有高级用户要按 path 前缀分流、按 header 路由、灰度权重这些花活，给他们 `routing.mode=External`：operator 退后一步，只管 DNS、证书、Gateway、保护这些"平台契约"，VirtualService 让他们自己写，挂到 operator 管的 Gateway 上。同一个抽象，同时服务"什么都不想懂的人"和"什么都想自己控的人"。域名管理和流量管理正交。至于金丝雀、灰度、按 header 路由到测试环境这类需求，我们故意没在 CRD 里实现，而是留给 External，这背后有个关于产品生命周期的判断，[放到文末专门讲了](#灰度发布那是产品毕业以后的事)。

**约束写进类型，不写进代码。** spec 上那条 `XValidation` 在 API 边界（CEL）就把"Managed 必须恰好一个 backend、External 必须没有 backend"这条规则钉死。配错的 CR 根本进不来，`kubectl apply` 当场被拒，连 reconcile 都不会触发。把不变量放进类型、而不是放进 operator 里事后检查，意味着用户在提交那一刻就拿到反馈，而不是过一会儿去翻 status 才发现没生效。这对一个"给非专家用"的自助平台尤其重要：错误要在最早、最靠近用户的地方暴露。

合起来：一个 DomainRoute 就是领域专家和底层那一堆 Istio / DNS / 证书对象之间唯一的接口。他填一张表，operator 把它翻译成 DNS 记录、Gateway、VirtualService、ServiceEntry、AuthorizationPolicy、EnvoyFilter 里的一条……这些名词，他一个都不用知道。

## 对内、对外，和"自助配保护"这件危险的事

先说对内对外。CR 里有个必填字段 `lb` 枚举：`alb-out`（走公网 ALB）或 `alb-in`（走内网 ALB）。特意把它设成必填、没有默认值。暴露面这种事，不该靠"忘了填"来决定。需要得明确说出"这东西要对公网开"，而不是让系统替你默认一个。

网关保护也很重要。产品大跃进之下，每个应用各自维护一套用户/鉴权系统，既荒谬又不安全。一个域名可以挂上网关级的鉴权，走 Istio 的 ext_authz：operator 给这条 DomainRoute 生成一条 `AuthorizationPolicy`，动作是 `CUSTOM`，指向一个预先在 mesh 里注册好的外部鉴权 provider。请求进来，网关拿它去问鉴权服务做 AuthN 校验。

一个典型请求在网关里大致是这么走的：

{{< mermaid >}}
sequenceDiagram
participant C as 客户端
participant GW as Ingress 网关
participant AUTH as 外部鉴权 provider
participant BE as 后端服务

    C->>GW: 请求，可能自带伪造的 x-app-id
    Note over GW: Lua 按 Host 查表<br>命中则改写 x-app-id 为真值<br>未命中则删除该 header
    GW->>AUTH: ext_authz 询问，带网关盖章的 x-app-id
    AUTH-->>GW: 准入 / 拒绝
    GW->>BE: 仅在准入时放行
    BE-->>C: 响应

{{< /mermaid >}}

调用方的身份是网关说了算的，不是客户端能自己塞的。

operator 维护一个集群唯一的 EnvoyFilter，在 ingress 网关上挂一段 Lua，插在 ext_authz 过滤器之前。这段 Lua 按请求的 Host 查一张 `host → 身份` 的表（姑且把这个身份 header 叫 `x-app-id`）：命中就把 `x-app-id` 强制改写成该 Host 对应的值，没命中就直接删掉这个 header。于是：

- 客户端自己伪造一个 `x-app-id` 传进来没用。网关在把请求交给鉴权服务之前，会用 Host 对应的真值覆盖它、或者抹掉。鉴权服务看到的身份永远是网关生成的。
- 这张表由所有 DomainRoute 的 `protection.appId` 聚合而成。两个域名要是填了同一个身份，谁都不生效。冲突双方一起被踢出表，各自的 DomainRoute 报 `ProtectionReady=False / AppIDConflict`。宁可两个都不放行，也不放一个有歧义的身份进去。AppID 由 App 管理平台生成、在 UI 层自动填好，正常路径下用户碰不到它，也就填不错。
- provider 名字要是写错、指向一个没注册的鉴权服务？`AuthorizationPolicy` 照样生成，而 ext_authz 在 provider 不存在时是拒绝一切的。配错的结果是"全关"，不是"全开"。

这几条是同一个原则：只要和安全沾边，出错的方向必须倒向"更关"而不是"更开"（fail closed）。自助平台最怕的就是有人点几下把服务暴露，所以默认值、冲突、配错，统统倒向保守那一侧。

鉴权服务凭什么拿这个身份决定放不放行？前提是我们在做这套东西之前，已经把全公司的账号体系打通了：整个公司域内是同一套账号，用户登录拿到的 JWT 带着一组放行的 app id。网关把 `x-app-id` 盖在请求上之后，鉴权服务要做的就只剩一件事：看一眼令牌里那组 app id，包不包含这个 `x-app-id`。App 平台控制"从 A 到 B 是否需要重新登录"。这种更灵活控制的单点登录在业务上更加明确产品的边界。

顺带一提，那张 host→身份 的表 operator 还会镜像一份到 ConfigMap 里，给平台 UI 和人审计用（Envoy 不读它）。数据平面的真相在 EnvoyFilter，这份只是个给人看的可读视图，两者分开，免得有人改了审计视图以为改了实际生效的东西。

### 增删一个 app，我们不去改脚本

你可能会问：如果频繁增加/下线产品，这张 host→身份表怎么维护？我的选择是"不进行增量维护"。

负责这件事的是一个集群级的聚合 controller。它的 reconcile 不关心到底是哪个 DomainRoute 变了。每次被触发，它就把集群里所有 DomainRoute 列一遍，重新算出完整的 host→身份 映射，重新渲染整段 Lua，整体覆盖那个 EnvoyFilter（和那份审计 ConfigMap）。对APP的CRUD，走的都是同一条路。重算全量，覆盖。

这听起来"浪费"（实际上并不会）。它换来的是幂等和自愈。增量去改一段共享的脚本，恰恰是 bug 的温床。漏删、覆盖、顺序错、状态漂移。而"拿etcd当唯一事实来源、每次重算"意味着：不管中间发生过什么，发布出去的表永远精确等于当前这批 DomainRoute。连冲突检测（同一个身份被两个域名占用）也是每次重算时一并算出来的，不存在"加进去那一刻漏检"。

所有事件，DomainRoute 变化、甚至 EnvoyFilter / ConfigMap 自己被改，都汇聚到同一个 workqueue key 上。于是一次批量变更（比如一口气迁几十个域名）被合并成一次重算，而不是几十次。性能上就我们这点体量，几十次全量重算也压根不算事，省下的开销不值一提；真正的价值在正确性。所有变更从同一个 key 串行进入，任何时刻只有一个 reconcile 在写那个全局唯一的 EnvoyFilter，不会出现几十个事件并发跑、一起抢写同一个对象的竞态。而"合并掉中间那些事件也不丢状态"之所以成立，恰恰是因为每次 reconcile 都重新全量读、全量算：它产出的永远是当前这批 DomainRoute 的完整结果，跟它跳过了多少次中间触发无关。

最后一点正好踩在本文的主线上：这个 controller 盯着自己产出的那个 EnvoyFilter 和 ConfigMap。谁要是手动改了、或者误删了，它立刻把它们 reconcile 回应有的样子。实际上在我们这波对基础设施的升级中就有因为[istio升级造成的雪崩](#istio-升级引发的雪崩)。Root Cause 就是"手工改的配置没有声明式来源、一次重建就丢了"。这套 controller 死盯着自己的产出，就是同一个教训的正面落实。

这套做法存在天花板。身份表是直接内联成 Lua、烘焙进 EnvoyFilter 的。好处是请求路径上零外部查找，查表纯内存 `O(1)`，鉴权身份不依赖任何运行时调用。代价是整张表会随 xDS 推送给每一个 ingress 网关：几十个域名时毫无感觉，一旦到了上千规模，这个对象本身变大、每次增删都要把整段脚本重新下发，配置体积和推送成本就会开始有感。真到那一天，该做的是把身份查找从内联 Lua 里挪出去——比如让 ext_authz provider 自己根据来源解析身份，或者换一个共享的查找数据源。但我们离那个量级还很远，所以选了最简单、十行 Lua 能讲清的那个。不为想象中的规模提前买单，也是一种设计纪律。

`lb`（暴露面）和 `protection`（要不要鉴权）在 CR 里是两个独立字段，没有硬绑定。光看 CRD，你完全可以把一个域名设成 `alb-out`（公网）却不配 protection，得到一个公网可达、没有鉴权的端点。

这是故意的。强制"公网必须配保护"这条策略，我们放在产品中台的 UI 层。领域专家在网页上选了"对公网开放"，界面就强制他必须同时选好鉴权方式，走不到不配保护那一步。而 CRD 本身保持正交：机制层只负责"能表达任意组合"，要不要禁止某些组合是策略层的事。把策略放在人交互的那一层、把机制留在底层保持灵活，这样以后策略变了（比如某类内部公开 API 想豁免），不用动 CRD 和 operator。

## 为什么自己造，而不是用现成的

域名和流量管理可以切得很干净：DP转发流量、终止 TLS、跑过滤器；CP把 DNS、证书、网关、保护按一个产品的需要拼到一起。

**DP：Istio，因为它早就在了。** 做 DomainRoute 之前，我们已经在 Istio 上跑了两年多的服务网格，mesh、mTLS、可观测性都在上面。网关复用同一套数据平面，意味着不用再立第二套要学、要运维、要排障的技术栈，ext_authz 又是 Envoy 原生的扩展点，拿来即用。所以这一层其实谈不上选型。Kong、APISIX 都能干这些事。要是我们当初没在用 Istio，这个决定可能完全是另一个样子。

还有一层现实：我们的基础设施本身就摊在不同的云厂商上，前面说过，DNS 在一个云、LB 在另一个云，集群外还散着一批托管虚拟机。这种跨云的摊法下，一个厂商中立的数据平面格外值钱：流量入口、路由、鉴权这些都收在 Istio 里，而不是绑死在某一家云的专有网关产品上。底座是谁，对上层那套抽象基本透明。

**CP：这才是真正需要解释的——为什么不用现成的，而是自己写一个 CRD。** DNS 有 external-dns，证书有 cert-manager（我们就在用），网关路由有 Gateway API。单看每一块，轮子都有人造好了。但它们有个共同的隐含前提：后端是 k8s 里的东西。external-dns 盯着 Ingress/Service 同步 DNS，Gateway API 的 HTTPRoute 指向的是 k8s Service。可一旦我要把一个域名指到一台不在集群里、不归 k8s 管的虚拟机上（还记得死活不上 k8s 的吗），这些 k8s-native 的工具就开始别扭，甚至失效。

我们要的是一个业务语义的高层对象：一个产品要一个域名、对内还是对外、后端在哪（管它在不在 k8s）、要不要保护——填一张表，剩下的 DNS 记录、证书覆盖、Gateway、VirtualService、ServiceEntry、AuthorizationPolicy 全由 operator 拼出来。现成的底层资源给不了这个抽象层次，它们是积木，我们要的是一键成型。

那为什么不是"一层 Helm 模板生成器 + 一个校验 webhook"就算了？因为那种东西只在提交那一刻吐一坨 YAML，之后就不管了。而我管的状态有一半在 k8s 之外——DNS 记录、云 LB 上的证书、外部虚拟机的可达性。这些会漂移、会被人手改、会过期。需要的是一个持续 reconcile、不断把现实拉回声明的控制循环，这正是 operator 的本职，也是一次性生成器给不了的。

### 那 kro / Kratix / Crossplane 呢？

kro 是纯组合。一张 ResourceGraphDefinition 把若干 k8s 资源拼成一张图。它对集群外的事没有任何主张，而我一半的活儿恰恰在集群外: 调 DNS 厂商的 API、把证书推到另一个云的 LB、把虚拟机注册进网格。我们可以让 kro 去组合 Crossplane 的 managed resource 来兜命令式那半，可那样一来 kro 从来就不是候选，Crossplane 才是。于是又回到下面那个问题(何况 kro 还很新)。所以 kro 不是被单独排除，是和 Crossplane 栽在同一件事上。

Kratix 完全做得到——Promise 的设计就是为了"自助交付一个横跨 k8s 和外部资源的东西"。代价是它是一整层平台：一套 opinionated 的 GitOps 管线，压在我已经在跑的 Istio 和 GitOps 栈上面。不是它不行，是为一个一张 CRD 就能覆盖的问题，多养一套平台不划算。

Crossplane 是最难取舍的一个。它是真能跨云：DNS 记录、甚至云 LB，都能干净地建模成 managed resource，再用 Composition 拼起来。它不合适的原因不是能力，是形状。Crossplane 的模型是一个 claim 扇出它自己那组资源。我要的恰好相反，全集群每个 DomainRoute 收敛成一个全局唯一的 EnvoyFilter，而且(这一点没得商量)判断两个域名是否声明了同一个身份，本质上就是一次全局计算。不管你把数据面对象怎么切，总得有个组件同时看到所有 DomainRoute 才能抓到这个冲突。就算用 extra-resources 让 composition function 读到兄弟资源，那也变成 N 个 per-claim reconcile 抢着重写同一个全局对象。你真正要的是一个串行的聚合器独占那个单例。于是你还是得另写这个 controller，同时背两套范式:Crossplane 管简单那半(DNS、证书、网关)，手写 reconcile 管难那半。

实话实说，把全局聚合这个需求拿掉，只是"每个产品拼一套自己的 DNS + 证书 + 网关"，Crossplane 就是个正经选择，"我们自己造"这个决定也会弱很多。我们需要这个跨 CR 的冲突检测。

## 可观测性接入

自助上线还有个容易被忽略的后半句：上线之后呢？一个人把产品发出去了，出问题谁知道、怎么查？所以一个域名在 DomainRoute 生效的同时，就被自动接进了可观测性——访问日志、请求里注入的 trace_id、错误率指标的采集和告警，一样都不用他自己配。

这对集群外那些虚拟机后端尤其重要。k8s 里的服务自带一层自愈：探针挂了会重启，节点没了会重新调度。可跑在虚拟机上的服务没有这层兜底，进程死了就是死了，没人帮它拉起来。所以对它们来说，可观测性和告警不是锦上添花，而是替代了一部分本该由 k8s 提供的健康保障。既然没有自愈，那至少要第一时间知道它出事了。统一接入可观测性，某种程度上是在替这些"不肯上 k8s"的服务，补回它们自己放弃掉的那张安全网。

## 迁移中的坑

通配不是银弹，总有它盖不住的。多级子域名（`a.b.example.com`）不在一张 `*.example.com` 里。这些我们没硬塞进通配体系，留了旁路单独签、给例外留通道，比假装一套方案包打天下健康得多。前面提过的 CDN 也是同理，它走自己的证书，配置又很少动，不值得纳进来。

把存量那些虚拟机上的服务搬进来是另一类活。它们得先被注册成 ServiceEntry 才能进网格，这中间网络要先打通（VPC 可达、安全组放行），否则 operator 把对象都建好了，流量还是过不去。

### Istio 升级引发的雪崩

前面提了一句那场雪崩，它正好是这篇文章所有"声明式"主张的反面教材。

先交代大环境：Istio 版本迭代很快，旧版本 EOL 的压力是真实的。我相信大量的服务跑的 Istio 都是 EOL 的，我们升级前用的甚至是 1.13。 `istioctl` 升级，升完没多久，新 Pod 开始调度失败。

排查的过程有点意思，因为第一反应是错的。先看节点资源，CPU、内存用量都正常，Pod 就是调度不上去。 `kubectl describe node | grep -E "^(Name:|  cpu )" -C 2 `发现节点的资源 request 已经打满了，而实际用量并不高。

那 request 怎么突然涨上去的？因为istio升级后滚动时也更新了sidecar。之前某个同事手工压低过 sidecar 的资源规格，但这个调整从来没固化成声明式配置。`istioctl` 升级会重建 sidecar 的注入模板，于是那个手工压低的值丢了、回退成默认值，每个 Pod 的 sidecar 凭空胖了一圈，全集群的 request 预留瞬间被顶满。

止血是这么做的：先紧急加节点，腾出调度空间；把流量手动引到还能跑的实例上；等服务稳定下来，再慢慢驱逐、滚动恢复。中间还有个尴尬之处。因为新 Pod 调度不上去，连"把 sidecar 规格改回正确值"这件事本身都一度推不下去（它也得调度一个新 Pod 才能生效），有点鸡生蛋。

事后复盘，表象是 sidecar 膨胀，根因是那份配置没有声明式的 source of truth。一个在稳定运行时谁都不会注意的手工值，在一次重建里就把整个集群干趴了。在某些地方记录"下次记得改回来"没什么意义，那等于把同一颗雷重新埋一遍。把 IstioOperator（iop）的配置纳入 GitOps 仓库，让它成为唯一事实来源：升级前能 diff，升级后会被持续校准，不靠某个人的脑子记住它。

这件事的教训，和前面那个"增删 app 不改脚本、整张表重算"的设计其实是同一句话的两面：任何靠手工生效、没有声明式来源的配置，都是一颗定时炸弹。区别只在于，这次我们是被它炸过之后，才真正把这句话刻进去的。

## 效果与反思

先说效果。上线一个新应用完全自我闭环，不再有半夜"帮我配一个域名"；证书从"每域名一张、人工续"变成一张通配自动续，过期事故归零。这套东西现在管着60个域名，背后既有 k8s 里的服务，也有集群外的虚拟机。

天下没有白来的抽象。我们目前还有两块没收干净。

证书其实是两套：边缘那张通配证书由一个独立签发器签发、再推送到云 LB；mesh 内的 mTLS 走 cert-manager。要不要把它们收敛成一套，是清单上的事。但 cert-manager 签完证书就停在 k8s Secret，把证书送上云 LB 这一步它不管，得自己补一个同步器。这一步是那个独立签发器至今没被替掉的原因。

另一块是协议。DomainRoute 今天只管 HTTP(S)。TCP（比如 GitLab 的 git over SSH）还走一个独立的 CLB，没做进来，CRD 里给 `protocol` 留了 `TCP` 的口子，但目前只有一个服务需要它，YAGNI，等真有第二个 TCP 需求再接。

### 灰度发布？那是产品毕业以后的事

有人问过：能不能在平台里做金丝雀、灰度，能不能接 Argo Rollouts 那种指标驱动的渐进式发布？

能，但不在 Managed 模式里做，而是走 External。应用团队自己带 Argo Rollouts，让它去拥有、改写 VirtualService，operator 只继续守着 DNS、证书、Gateway、保护这几样不变的东西。这样就不会出现"operator 和 Rollouts 抢着写同一个 VirtualService"的双写打架。

但我更想说的是背后那条线：需要灰度，本身就说明这个产品已经毕业了。这套自助抽象服务的是 0 到 1。某个人有个想法，想快点让它跑起来、给人看。而当一个产品要认真做金丝雀、要盯着指标一步步放量，往往意味着它已经正式发布、已经被验证有价值、已经有专业的人进场接手了。到那个阶段，他们既不需要、也不应该再被那套"什么都不用懂"的表单兜着。他们有能力、也理应自己拥有 VirtualService 和发布流程。在CRD中重建一整套Argo Rollouts原语是荒谬的。某种程度上我们这种产品大跃进本身也是快速试错的体现。

## 结语

回头看，这套东西的内核其实很简单：把一件原本需要提工单、需要等人的事，变成填一张表、机器来做。域名、证书、网关、保护，这些名词领域专家一个都不用懂，他们只是想让自己的产品被人访问到，那本就该这么简单。

但写到这儿我更想说的是另一半：这篇里反复出现的，不是"我们支持了多少功能"，而是一串"我们故意没做什么"。能往一个抽象里塞多少东西从来不是难点；难的是想清楚它为谁服务、到哪儿为止。
