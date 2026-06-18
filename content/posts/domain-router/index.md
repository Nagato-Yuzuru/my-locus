---
title: "Turning Infrastructure into a Product: Letting Domain Experts Self-Serve with a CRD"
date: 2026-05-25T12:16:11+08:00
draft: false
description: "From one cert per domain to DomainRoute: how we used a single CRD to hide the difference between k8s and non-k8s backends, let domain experts ship from a web page, and every pit we fell into along the way."

# Tags MUST be from data/tags.yaml — CI will reject unknown tags.
tags: ["devops", "cloud-native"]

# Optional: group post into a named series (free-form, no whitelist).
# Example: series: ["Tokio Deep Dive"]
# series: []
---

## Background and constraints: why we had no choice

I work at a vertical SaaS and platform company in weather-data and algorithm-driven energy futures trading. The business and its requirements lean heavily on domain experts' trading and market knowledge. Agentic coding has been a huge productivity boost for us. Domain experts and traders can now point an AI at their own needs and pain points and get a product built fast.

We used to run 2-3 core products. With this burst of productivity the count grew very quickly (an aside: my boss has hacked together a lot of internal services. Some are genuinely useful. But most feel closer to "a Grafana with a flashier UI that you can click around in"). And the speed of getting a product up for testing kept climbing too.

The way we collaborate changed with it. It used to be sliced by role: dev, ops, product, each owning a segment. Now it's "whoever has the idea builds it, ships it, and maintains it themselves." Ideally, at least before a formal release, one person can close the loop from "I want a thing" all the way to live. The problem is that domains, certs, all that stuff in the old pipeline simply can't keep up with this style of play. And there's a painful reality: domain experts (and part of the algo team) are fairly "allergic" to k8s. They've got a good number of services deployed on cloud-managed VMs. They don't want to learn these dizzying "relics," and we (or any sane engineer) would never hand gateway/domain/cert config to whatever AI any random person in the company happens to be using.

Obviously, domain and gateway config was going to become the thing that blocked the loop from closing.

## A new product needs to go live

The old way: a new product launch meant someone dedicated (though most of the time it was a dev moonlighting as ops) doing the deploy, gateway config, domain binding, DNS changes, and so on. Cycle measured in months. It's different now. I watched, firsthand, people who previously had no real engineering ability discover that an Agent could turn their idea into a basically-usable product in no time. A lot of them showed a kind of fervor, almost an addiction. If your boss calls you up four or five nights in one week to help him configure a domain, you'll feel in your bones that this approach doesn't scale.

We needed a way that's good for everyone, where this annoying stuff gets handled self-service in five minutes on our management platform's web page (personally I of course love YAML config and a CLI. My vim and shell are razor-sharp. But the domain experts and the boss almost certainly don't see it that way).

## Network topology: one wildcard holding up every product

Before getting into the CRD, let me lay out the current network architecture concretely.

{{< mermaid >}}
flowchart TB
dom["product domain<br>CNAME created by operator"]
dom -->|"lb=alb-out"| albout["alb-out<br>public ALB"]
dom -->|"lb=alb-in"| albin["alb-in<br>internal ALB"]

    albout --> igw["istio-ingressgateway"]
    albin --> igw

    igw --> route["one Gateway + VirtualService per domain<br>operator generates by host"]

    route --> ksvc["k8s Service<br>in-cluster backend"]
    route --> se["ServiceEntry<br>to out-of-cluster VM"]

    cert["wildcard cert *.example.com<br>auto-issued + renewed"] -. TLS termination .-> albout
    cert -. TLS termination .-> albin

{{< /mermaid >}}

The shape is simple. Two ALBs, one facing the public internet (alb-out), one internal (alb-in). Behind them sits the same Istio IngressGateway, splitting by Host to each product. Which ALB a product's domain goes through is decided by one field in the CR (`lb`). The operator creates a CNAME for that domain pointing at the corresponding ALB's record.

The convenience comes down to two pieces of automation. First, a new product wants `newthing.example.com` and nobody has to touch DNS by hand. The operator calls the DNS vendor's API and sets up that CNAME pointing at the ALB. Second, the ALB carries a `*.example.com` wildcard cert, so a new subdomain's TLS is covered directly with nothing to issue separately. Anything that needs a process, the operator does.

There's a point about certs that's easy to get wrong, so let me clear it up: TLS terminates at the ALB, and the Istio gateway only does HTTP host routing. So the "cert" thing happens at the cloud ALB, not inside the mesh. And there's a real little annoyance: our DNS and our LB aren't with the same cloud vendor. The DNS-01 challenge hits cloud A's DNS, and the cert that comes out has to be pushed onto cloud B's LB, and you have to wire up that cross-cloud link yourself. Before this we ran one cert per domain, uploaded by hand, and the occasional forgotten renewal meant getting an expiry alert at midnight, or worse, being told by a customer.

### What this topology costs

The convenience the wildcard buys is paid for with a few new risks:

- The wildcard's blast radius. Leak the private key of one `*.example.com` and every product under that suffix goes down together. Convenience and blast radius are two sides of the same coin.
- The wildcard only covers one level. `*.example.com` doesn't match `a.b.example.com`. Products that need multi-level subdomains have to be handled separately.
- The CDN runs its own cert. CDN-related network config changes very rarely, though. Leaving it out of this system is, I think, the right call.
- DNS-01 needs write access to DNS. A wildcard can't use HTTP-01, only DNS-01, which means the issuance flow is holding an API token that can change DNS records. One more high-privilege credential to guard carefully.
- Shared ingress == shared fate. All product traffic squeezes through the same IngressGateway, so one product's misconfiguration or traffic spike will, in theory, hit the neighbors. The ops simplification from consolidation is paid for by putting the eggs in one basket, and that basket's resilience (replicas, multi-AZ, health checks) has to be worked on on its own.

## A unified abstraction: one CR hides k8s and non-k8s backends

The core of all this: the `DomainRoute` CR. One DomainRoute describes one fully managed domain: the DNS record, the cert coverage bound to the ALB, the matching Istio Gateway and VirtualService, and optional gateway protection. The form a domain expert fills in on the web page is backed by exactly this (convincing the colleague who owns the management platform to add a k8s SDK dependency, rather than wrapping yet another API service around the APIService, was an uphill battle. They'd treat the inside of k8s as a mysterious black box and refuse to bring in the dependency. I pulled it off).

The spec looks roughly like this:

<details>
<summary>Expand the Go type definitions for DomainRoute</summary>

```go
// LBSelector decides which ALB the traffic takes: public or internal.
// +kubebuilder:validation:Enum=alb-out;alb-in
type LBSelector string

const (
	LBALBOut LBSelector = "alb-out" // public ALB
	LBALBIn  LBSelector = "alb-in"  // internal ALB
)

// ServiceBackend: an in-cluster Kubernetes Service.
type ServiceBackend struct {
	// +kubebuilder:validation:Required
	Name string `json:"name"`
	// Set this when crossing namespaces; leave empty to use the DomainRoute's own namespace.
	// +optional
	Namespace string `json:"namespace,omitempty"`
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=65535
	Port int32 `json:"port"`
}

// ExternalBackend: an out-of-cluster VM endpoint. The operator uses an Istio ServiceEntry
// to register it as a routable target in the mesh. IPv4 only, no DNS resolution.
type ExternalBackend struct {
	// +kubebuilder:validation:Pattern=`<IPv4 dotted decimal>`
	IP string `json:"ip"`
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=65535
	Port int32 `json:"port"`
	// +kubebuilder:validation:Enum=HTTP;HTTPS;TCP
	// +kubebuilder:default=HTTP
	Protocol string `json:"protocol,omitempty"`
}

// Backend is a discriminated union: at most one of service or external is set.
// +kubebuilder:validation:XValidation:rule="!(has(self.service) && has(self.external))",message="at most one of service or external may be set"
type Backend struct {
	// +optional
	Service *ServiceBackend `json:"service,omitempty"`
	// +optional
	External *ExternalBackend `json:"external,omitempty"`
}

// RoutingMode: who owns the VirtualService.
// Managed (default) = operator generates it; External = the app team writes it.
// +kubebuilder:validation:Enum=Managed;External
type RoutingMode string

// ProtectionSpec: optional gateway auth.
type ProtectionSpec struct {
	// Name of an external auth provider pre-registered in the mesh; unknown means fail closed.
	// +kubebuilder:validation:Required
	Provider string `json:"provider"`
	// Caller identity, globally unique; a duplicate means ProtectionReady=False / AppIDConflict.
	// +kubebuilder:validation:Required
	AppID string `json:"appId"`
    // Controls the specific protection method and the allowlisted URLs.
	// +optional
	Rules []ProtectionRule `json:"rules,omitempty"`
}

// DomainRouteSpec: one DomainRoute describes one fully managed domain.
//
//   - routing.mode=Managed (default): exactly one of backend.service / backend.external must be set.
//   - routing.mode=External: backend must be empty, the VirtualService is owned by the app team.
//
// +kubebuilder:validation:XValidation:rule="(has(self.routing) && self.routing.mode == 'External') ? (!has(self.backend) || (!has(self.backend.service) && !has(self.backend.external))) : (has(self.backend) && (has(self.backend.service) || has(self.backend.external)))",message="..."
type DomainRouteSpec struct {
	// e.g. api.example.com
	// +kubebuilder:validation:Required
	Domain string `json:"domain"`

	// +kubebuilder:validation:Required
	LB LBSelector `json:"lb"`

	// +optional
	Routing RoutingSpec `json:"routing,omitempty"`

	// Specifies the backend in Managed mode; must be empty in External mode.
	// +optional
	Backend Backend `json:"backend,omitempty"`

	// +kubebuilder:validation:Required
	DNS DNSSpec `json:"dns"`

	// If unset, the gateway lets traffic through directly (no auth).
	// +optional
	Protection *ProtectionSpec `json:"protection,omitempty"`
}
```

</details>

Let me pick out a few points I think matter most in the design.

**The single `backend` field is a concession to the people who won't move to k8s.** (You know how it goes: the harder someone is to persuade, the higher up the food chain they sit.) (Sadly, I couldn't talk him into deploying on k8s; the release primitives and self-healing are hard to replicate outside it.) This is the reason the whole thing exists. The backend is either a `Service` inside the cluster, or a VM outside it (`external` holds the IP, port, protocol). The operator eats the difference. If it's a Service, it points straight at that Service in the cluster; if it's external, the operator generates an Istio `ServiceEntry` that registers that not-managed-by-k8s VM as a routable target in the mesh. To the person filling in the form, "my thing runs in k8s" and "my thing is a VM" go in the same slot of the same form, and you get the same DNS, cert, gateway, and optional protection. The "hide the difference between k8s and non-k8s" from the opening, in practice, is this one discriminated union.

**Managed is the default, External is the escape hatch.** Most people just want "point this domain at my service," and the operator generates even the VirtualService for them, and they never have to know what Istio is. But there's always an advanced user who wants path-prefix splitting, header routing, canary weights, all that fancy stuff. Give them `routing.mode=External`: the operator steps back and only handles DNS, certs, Gateway, protection (the "platform contract"), and lets them write the VirtualService themselves, hung off the Gateway the operator manages. Same abstraction, serving both "the person who wants to understand nothing" and "the person who wants to control everything." Domain management and traffic management are orthogonal. As for canary, gradual rollout, and header-based routing to a test environment: we deliberately didn't put these in the CRD, leaving them to External instead, and behind that is a judgment about product lifecycle, [which I saved for the end](#canary-releases-thats-a-post-graduation-problem).

**Constraints go into the type, not into the code.** That `XValidation` on the spec pins down, right at the API boundary (CEL), the rule that "Managed must have exactly one backend, External must have none." A misconfigured CR doesn't even get in: `kubectl apply` is rejected on the spot, reconcile never even fires. Putting invariants into the type, rather than checking them after the fact inside the operator, means the user gets feedback the moment they submit, instead of digging through status a while later to find it didn't take. This matters all the more for a self-service platform "for non-experts": errors should surface at the earliest point, closest to the user.

Put together: one DomainRoute is the single interface between a domain expert and the pile of Istio / DNS / cert objects underneath. They fill in a form, and the operator translates it into a DNS record, a Gateway, a VirtualService, a ServiceEntry, an AuthorizationPolicy, a line in an EnvoyFilter… none of which they ever need to know.

## Internal, external, and the dangerous business of "self-serve your own protection"

First, internal vs. external. The CR has a required `lb` enum field: `alb-out` (public ALB) or `alb-in` (internal ALB). I made it required on purpose, with no default. Exposure surface isn't the kind of thing that should be decided by "forgot to fill it in." You need to explicitly say "this thing is open to the public internet," not let the system pick a default for you.

Gateway protection matters too. In the middle of a product great-leap-forward, having every app maintain its own user/auth system is both absurd and unsafe. A domain can have gateway-level auth hung on it, via Istio's ext_authz: the operator generates an `AuthorizationPolicy` for this DomainRoute, action `CUSTOM`, pointing at an external auth provider pre-registered in the mesh. A request comes in, the gateway takes it to the auth service for an AuthN check.

A typical request goes through the gateway roughly like this:

{{< mermaid >}}
sequenceDiagram
participant C as client
participant GW as ingress gateway
participant AUTH as external auth provider
participant BE as backend service

    C->>GW: request, possibly carrying a forged x-app-id
    Note over GW: Lua looks up by Host<br>on a hit, rewrites x-app-id to the real value<br>on a miss, strips the header
    GW->>AUTH: ext_authz query, with the gateway-stamped x-app-id
    AUTH-->>GW: allow / deny
    GW->>BE: pass through only on allow
    BE-->>C: response

{{< /mermaid >}}

The caller's identity is decided by the gateway, not something the client can stuff in itself.

The operator maintains one cluster-unique EnvoyFilter that hangs a bit of Lua on the ingress gateway, inserted before the ext_authz filter. This Lua looks up a `host → identity` table by the request's Host (let's call this identity header `x-app-id`): on a hit it force-rewrites `x-app-id` to the value for that Host, on a miss it just deletes the header. So:

- A client forging its own `x-app-id` and sending it in gets nothing. Before handing the request to the auth service, the gateway overwrites it with the real value for that Host, or wipes it. The identity the auth service sees is always the one the gateway generated.
- This table is aggregated from the `protection.appId` of every DomainRoute. If two domains fill in the same identity, neither takes effect. Both sides of the conflict get kicked out of the table together, and each DomainRoute reports `ProtectionReady=False / AppIDConflict`. Better to let neither through than to admit one ambiguous identity. The AppID is generated by the App management platform and auto-filled in the UI; on the normal path the user never touches it, so they can't get it wrong.
- The provider name is typo'd and points at an unregistered auth service? The `AuthorizationPolicy` is still generated, and ext_authz denies everything when the provider doesn't exist. The result of a misconfig is "all closed," not "all open."

These all come from the same principle: anything that touches security, the direction of failure must tip toward "more closed" rather than "more open" (fail closed). The thing a self-service platform fears most is someone clicking a few times and exposing a service, so defaults, conflicts, and misconfigs all tip to the conservative side.

What gives the auth service the right to decide pass/deny from this identity? The premise is that, before building any of this, we'd already unified the company's whole account system: one set of accounts across the entire company domain, and the JWT a user gets on login carries a set of allowed app ids. Once the gateway has stamped `x-app-id` onto the request, the only thing left for the auth service to do is glance at the set of app ids in the token and check whether it contains this `x-app-id`. The App platform controls "whether going from A to B needs re-login." This more flexible single sign-on draws clearer product boundaries on the business side.

By the way, the operator also mirrors that host→identity table into a ConfigMap, for the platform UI and for humans to audit (Envoy doesn't read it). The data-plane truth is in the EnvoyFilter; this copy is just a human-readable view, kept separate so nobody edits the audit view and thinks they've changed what's actually in effect.

### To add or remove an app, we don't edit a script

You might ask: if we're adding/retiring products often, how do we maintain this host→identity table? My choice is "don't maintain it incrementally."

The thing responsible is a cluster-level aggregating controller. Its reconcile doesn't care which DomainRoute actually changed. Every time it's triggered, it lists every DomainRoute in the cluster, recomputes the full host→identity mapping, re-renders the whole chunk of Lua, and overwrites that EnvoyFilter (and the audit ConfigMap) wholesale. CRUD on an app all goes down the same road. Recompute everything, overwrite.

This sounds "wasteful" (it really isn't). What it buys is idempotency and self-healing. Incrementally editing a shared script is exactly where bugs breed. Missed deletes, overwrites, ordering mistakes, state drift. Whereas "treat etcd as the single source of truth and recompute every time" means: no matter what happened in between, the published table is always exactly equal to the current set of DomainRoutes. Even conflict detection (the same identity claimed by two domains) is computed as part of each recompute, so there's no "missed the check at the moment it was added."

All events (DomainRoute changes, even the EnvoyFilter / ConfigMap themselves being edited) funnel onto the same workqueue key. So a batch change (say, migrating dozens of domains at once) collapses into one recompute instead of dozens. Performance-wise, at our scale, dozens of full recomputes are nothing, and the overhead saved isn't worth mentioning; the real value is correctness. Every change enters serially through the same key, so at any moment only one reconcile is writing that globally-unique EnvoyFilter, so no race where dozens of events run concurrently and fight to write the same object. And "collapsing the middle events without losing state" holds precisely because every reconcile re-reads and recomputes everything: what it produces is always the complete result for the current set of DomainRoutes, regardless of how many intermediate triggers it skipped.

The last point lands right on this post's main thread: this controller watches the EnvoyFilter and ConfigMap it produces. If anyone edits them by hand, or deletes them by mistake, it reconciles them right back to what they should be. Actually, during this round of infrastructure upgrades we had an [avalanche caused by an Istio upgrade](#the-avalanche-an-istio-upgrade-set-off). The root cause was "hand-edited config with no declarative source, lost on a single rebuild." This controller staring down its own output is the positive enactment of the same lesson.

This approach has a ceiling. The identity table is inlined into Lua, baked into the EnvoyFilter. The upside is zero external lookups on the request path, table lookup is pure in-memory `O(1)`, and auth identity doesn't depend on any runtime call. The cost is that the whole table gets pushed via xDS to every ingress gateway: at dozens of domains you feel nothing, but once you're at thousands the object itself grows, and every add/remove re-pushes the whole script, so config size and push cost start to be felt. When that day comes, the thing to do is move identity lookup out of the inlined Lua: say, let the ext_authz provider resolve identity from the origin itself, or switch to a shared lookup data source. But we're a long way from that scale, so we picked the simplest one, the one ten lines of Lua can explain. Not paying upfront for imagined scale is its own kind of design discipline.

`lb` (exposure surface) and `protection` (auth or not) are two independent fields in the CR, with no hard binding. Looking only at the CRD, you can absolutely set a domain to `alb-out` (public) with no protection configured, and get a publicly-reachable endpoint with no auth.

This is deliberate. The policy "public must have protection" we put in the product platform's UI layer. When a domain expert picks "open to the public internet" on the web page, the UI forces them to pick an auth method at the same time, so they can't get to the no-protection state. And the CRD itself stays orthogonal: the mechanism layer only handles "being able to express any combination," and whether to forbid certain combinations is the policy layer's business. Putting policy in the human-interaction layer and keeping mechanism flexible underneath means that when policy changes later (say, some class of internal-public API wants an exemption), you don't have to touch the CRD or the operator.

## Why we built our own instead of using something off the shelf

Domain and traffic management splits cleanly: the data plane forwards traffic, terminates TLS, runs filters; the control plane stitches DNS, certs, gateway, and protection together to fit one product's needs.

**Data plane: Istio, because it was already there.** Before DomainRoute, we'd been running a service mesh on Istio for over two years: mesh, mTLS, observability, all on it. Reusing the same data plane for the gateway means not standing up a second stack to learn, operate, and troubleshoot, and ext_authz is a native Envoy extension point, ready to use. So this layer wasn't really a decision. Kong and APISIX can all do this stuff. If we hadn't already been on Istio, this call might have looked completely different.

There's another layer of reality: our infrastructure is itself spread across different cloud vendors. As I said, DNS on one cloud, LB on another, and a pile of managed VMs scattered outside the cluster. With things spread cross-cloud like that, a vendor-neutral data plane is especially valuable: ingress, routing, auth are all kept inside Istio rather than nailed to one cloud's proprietary gateway product. Whoever the substrate is stays mostly transparent to the abstraction on top.

**Control plane: this is the part that actually needs explaining: why not use what's out there, and write a CRD instead.** DNS has external-dns, certs have cert-manager (we use it), gateway routing has Gateway API. Block by block, somebody's already built the wheel. But they share one implicit assumption: the backend is a thing inside k8s. external-dns watches Ingress/Service to sync DNS; Gateway API's HTTPRoute points at a k8s Service. The moment I want to point a domain at a VM that isn't in the cluster and isn't managed by k8s (remember the folks who won't touch k8s?), these k8s-native tools start to chafe, or just stop working.

What we wanted was a high-level object with business semantics: a product wants a domain, internal or external, a backend somewhere (k8s or not), protection or not. Fill in one form, and the rest (DNS record, cert coverage, Gateway, VirtualService, ServiceEntry, AuthorizationPolicy) all get stitched together by the operator. The off-the-shelf low-level resources can't give that level of abstraction. They're building blocks; we wanted one-press molding.

So why not just "a layer of Helm template generator + a validating webhook" and call it done? Because that kind of thing only spits out a pile of YAML at the moment you submit, and then it walks away. Half the state I care about lives outside k8s: DNS records, the cert on the cloud LB, the reachability of external VMs. These drift, get changed by hand, expire. What's needed is a control loop that keeps reconciling, continually dragging reality back to the declaration, which is exactly an operator's job, and exactly what a one-shot generator can't give.

### Why not kro, Crossplane, or Kratix

kro is pure composition. A ResourceGraphDefinition stitches k8s resources into a graph. It has no opinion about anything outside the cluster, and half my job lives there: calling the DNS vendor's API, pushing a cert onto another cloud's LB, registering a VM into the mesh. You can paper over that by having kro compose Crossplane managed resources for the imperative parts, but then kro was never really the candidate; Crossplane was, and we're back to the problem below (plus kro is young). So kro isn't ruled out on its own; it's ruled out by the same thing Crossplane is.

Kratix can absolutely do this — Promises are designed for exactly "self-serve a thing that spans k8s and external resources." The cost is that it's a whole platform layer, opinionated GitOps pipeline and all, stacked on top of the Istio and GitOps stack I already run. Not that it can't; that it's a second platform to operate for a problem one CRD covers.

Crossplane is the close call. It's genuinely cross-cloud: DNS records and even the cloud LB model cleanly as managed resources, and a Composition wires them together. The reason it doesn't fit isn't capability, it's shape. Crossplane's model is one claim fanning out into its own set of resources. What I need is the inverse: every DomainRoute in the cluster collapses into one globally-unique EnvoyFilter, and (this part isn't negotiable) detecting that two domains claimed the same identity is inherently a global computation. Something has to see all DomainRoutes at once to catch the conflict. A composition function could read its siblings via extra-resources, sure, but then you've got N per-claim reconciles all racing to rewrite the same global object. What you actually want is one serialized aggregator that owns that singleton. So you end up writing that controller anyway, and now you're maintaining two paradigms: Crossplane for the easy half (DNS, cert, gateway), hand-written reconcile for the hard half.

To be fair: drop the global aggregation, make it just "each product gets its own DNS + cert + gateway," and Crossplane is a perfectly sane choice; the "build our own" decision gets a lot weaker. It's the cross-CR conflict detection that tips the scale.

## Wiring in observability

Self-service launch has a second half that's easy to overlook: what happens after launch? Someone ships their product, and when something breaks, who knows, and how do they look into it? So the moment a domain goes live as a DomainRoute, it's automatically wired into observability: access logs, a trace_id injected into requests, error-rate metric collection and alerting, none of which they have to configure themselves.

This is especially crucial for those out-of-cluster VM backends. A service in k8s comes with a layer of self-healing: a failed probe restarts it, a dead node reschedules it. But a service on a VM has no such backstop. The process dies and it's just dead, nobody pulls it back up. So for them, observability and alerting aren't a nice-to-have; they replace part of the health guarantee k8s should have provided. Since there's no self-healing, at least know the instant it goes down. Wiring everyone into observability uniformly is, in a sense, restoring for these "won't move to k8s" services the safety net they gave up themselves.

## Pits hit during migration

The wildcard isn't a silver bullet; there's always something it can't cover. Multi-level subdomains (`a.b.example.com`) don't fall under one `*.example.com`. We didn't cram these into the wildcard system. We left a bypass to issue them separately and kept a channel for exceptions, which is far healthier than pretending one scheme handles everything. The CDN mentioned earlier is the same: it runs its own cert, its config rarely changes, and it isn't worth bringing in.

Moving the existing VM-hosted services in is another kind of job. They have to be registered as a ServiceEntry first to get into the mesh, and the network has to be opened up first (VPC reachability, security-group allow rules), otherwise the operator builds all the objects and the traffic still can't get through.

### The avalanche an Istio upgrade set off

I mentioned that avalanche above; it happens to be the counterexample to every "declarative" argument in this post.

First the backdrop: Istio iterates fast, and the pressure of an EOL'd version is real. I'm sure plenty of services out there are running EOL'd Istio; before our upgrade we were even on 1.13. `istioctl` upgrade, and not long after it finished, new Pods started failing to schedule.

The investigation was kind of interesting, because the first instinct was wrong. First I looked at node resources: CPU and memory usage both normal, Pods just wouldn't schedule. `kubectl describe node | grep -E "^(Name:|  cpu )" -C 2` showed the nodes' resource requests were already maxed out, while actual usage wasn't high.

So how did requests suddenly shoot up? Because the Istio upgrade also updated sidecars during the rollout. A colleague had once manually dialed down the sidecar's resource spec, but that adjustment was never solidified into declarative config. The `istioctl` upgrade rebuilds the sidecar injection template, so that hand-lowered value was lost, reverted to the default, every Pod's sidecar bloated out of nowhere, and the whole cluster's request reservation hit the ceiling in an instant.

Here's how we stopped the bleeding: add nodes urgently to free up scheduling room; manually steer traffic onto instances that could still run; once things stabilized, slowly evict and roll back to recovery. There was an awkward bit in the middle. Because new Pods couldn't schedule, even the act of "changing the sidecar spec back to the right value" couldn't be pushed through for a while (it also needs a new Pod scheduled to take effect), a bit of a chicken-and-egg.

In the post-mortem, the symptom was sidecar bloat, but the root cause was that config having no declarative source of truth. A manual value nobody would ever notice during stable operation took the whole cluster down in one rebuild. Writing "remember to change this back next time" somewhere is meaningless; that's just reburying the same mine. We pulled the IstioOperator (iop) config into the GitOps repo, making it the single source of truth: diff-able before an upgrade, continuously reconciled after, not reliant on someone's memory.

The lesson here is two sides of the same sentence as that earlier "add/remove an app without editing a script, recompute the whole table" design: any config that takes effect by hand, with no declarative source, is a time bomb. The only difference is that this time we got blown up before we really carved that sentence in.

## Results and reflections

The results first. Launching a new app fully closes its own loop: no more midnight "help me configure a domain"; certs went from "one per domain, renewed by hand" to one wildcard auto-renewed, and expiry incidents dropped to zero. This thing now manages 60 domains, backed by both in-cluster services and out-of-cluster VMs.

There's no free abstraction. We still have two corners we haven't cleaned up.

Certs are actually two sets: the edge wildcard is issued by a standalone issuer and then pushed onto the cloud LB; the in-mesh mTLS goes through cert-manager. Whether to converge them into one set is on the list. But cert-manager stops at a k8s Secret once it's issued a cert; getting the cert onto the cloud LB is a step it doesn't handle, so you have to add a syncer yourself. That step is why the standalone issuer hasn't been replaced to this day.

The other corner is protocol. DomainRoute today only handles HTTP(S). TCP (say, GitLab's git over SSH) still runs through a separate CLB, not brought in. The CRD left a `TCP` opening in `protocol`, but only one service needs it right now (YAGNI), so we'll wire it up when there's actually a second TCP need.

### Canary releases? That's a post-graduation problem

People have asked: can we do canary and gradual rollout in the platform, can we hook up something like Argo Rollouts for metric-driven progressive delivery?

We can, but not in Managed mode; it goes via External. The app team brings their own Argo Rollouts and lets it own and rewrite the VirtualService, while the operator keeps guarding the things that don't change: DNS, certs, Gateway, protection. That way you never get "the operator and Rollouts both fighting to write the same VirtualService," a double-write brawl.

But what I really want to point at is the line behind it: needing canary is itself a sign the product has graduated. This self-service abstraction serves 0 to 1. Someone has an idea, wants to get it running fast and put it in front of people. And when a product is going to seriously do canary, watch metrics, and ramp up step by step, it usually means it's already formally released, already validated as valuable, already has professionals on the scene to take over. At that stage, they neither need nor should still be cradled by that "understand nothing" form. They're capable of, and ought to, own the VirtualService and the release flow themselves. Rebuilding a whole set of Argo Rollouts primitives inside a CRD is absurd. In a way, our product great-leap-forward is itself an expression of fast trial-and-error.

## Closing

Looking back, the core of this thing is actually simple: take something that used to need a ticket and a wait for a person, and turn it into filling in a form and letting a machine do it. Domain, cert, gateway, protection: a domain expert needs to understand none of these nouns. They just want their product to be reachable, and that should have been this simple all along.

But writing this far, what I really want to say is the other half: what recurs in this post isn't "how many features we supported," it's a string of "things we deliberately didn't do." How much you can stuff into an abstraction was never the hard part; the hard part is thinking clearly about who it serves and where it stops.
