# Harbor Prometheus Alerts

Ready-to-use [Prometheus](https://prometheus.io) alerting rules for [Harbor](https://goharbor.io), the CNCF container registry. Copy the whole file, copy a single alert, or use it as inspiration for your own rules.

- 20 alerts across availability, core API, registry, jobservice, capacity and process health
- Plain Prometheus rules file and a Prometheus Operator `PrometheusRule`
- Unit-tested with `promtool`
- Based on the [Harbor metrics documentation](https://goharbor.io/docs/latest/administration/metrics/).

> Every threshold is a sensible starting point, not a universal truth. Tune them to your traffic and storage backend.

## Quick start

### 1. Make sure Harbor metrics are scraped

Enable metrics in `harbor.yml` or set `metrics.enabled: true` in the Helm chart, then scrape the `exporter`, `core`, `registry` and `jobservice` components. See the [official docs](https://goharbor.io/docs/latest/administration/metrics/#scraping-metrics-with-prometheus) for the scrape config and `ServiceMonitor`.

### 2a. Plain Prometheus

```yaml
# prometheus.yml
rule_files:
  - /etc/prometheus/rules/harbor-alerts.yaml
```

```bash
cp rules/harbor-alerts.yaml /etc/prometheus/rules/
promtool check rules /etc/prometheus/rules/harbor-alerts.yaml
```

### 2b. Prometheus Operator / kube-prometheus-stack

```bash
kubectl apply -n monitoring -f kubernetes/prometheusrule.yaml
```

kube-prometheus-stack only loads rules whose labels match its `ruleSelector` (by default `release: <helm-release-name>`). If the alerts do not show up, label the object:

```bash
kubectl -n monitoring label prometheusrule harbor-alerts release=kube-prometheus-stack
```

## Alerts

| Alert | Severity | Fires when |
|---|---|---|
| `HarborMetricsMissing` | critical | `harbor_health` is absent: exporter down, or it cannot reach Harbor core |
| `HarborUnhealthy` | critical | Harbor health API reports unhealthy |
| `HarborComponentDown` | critical | `core`, `database`, `redis` or `registry` is down |
| `HarborAuxiliaryComponentDown` | warning | `jobservice`, `portal`, `registryctl` or `trivy` is down |
| `HarborScrapeTargetDown` | warning | a Harbor scrape target has `up == 0` |
| `HarborCoreHighErrorRate` | critical | more than 5% of core API requests return 5xx |
| `HarborCoreSlowRequests` | warning | mean latency of an API operation above 5s |
| `HarborCoreInflightRequestsHigh` | warning | more than 100 concurrent requests in core |
| `HarborRegistryHighErrorRate` | critical | more than 5% of registry requests return 5xx |
| `HarborRegistrySlowRequests` | warning | p95 latency of a non-blob registry handler above 5s |
| `HarborRegistryStorageSlow` | warning | p95 latency of a storage driver action above 10s |
| `HarborJobQueueLatencyHigh` | warning | oldest queued job of a type has waited more than 10 min |
| `HarborJobQueueBacklog` | info | more than 1000 queued jobs of a type for 30 min |
| `HarborJobsFailing` | warning | more than 25% of a job type failed in the last hour (min. 5 tasks) |
| `HarborGarbageCollectionFailed` | warning | a garbage collection run failed in the last hour |
| `HarborProjectQuotaNearLimit` | warning | project between 85% and 100% of its quota |
| `HarborProjectQuotaExceeded` | critical | project reached 100% of its quota (pushes fail) |
| `HarborProjectQuotaWillFillSoon` | info | linear prediction says the quota fills within 7 days |
| `HarborProcessFileDescriptorsHigh` | warning | a Harbor process uses more than 80% of its file descriptors |
| `HarborProcessRestarting` | warning | a Harbor process restarted 3+ times in 30 min |

## Customising

- **Job names.** Only `HarborScrapeTargetDown`, `HarborProcessFileDescriptorsHigh` and `HarborProcessRestarting` reference job names (`job=~".*harbor.*"`). Change that matcher if your jobs are named differently.
- **Several Harbors in one Prometheus.** Add your identifying label (`cluster`, `namespace`, ...) to the `by (...)` and `on (...)` clauses.
- **No Trivy?** Remove `trivy` from the regex in `HarborAuxiliaryComponentDown`.
- **Alertmanager.** Route on `severity`. A useful inhibition so a total outage does not also page for every sub-alert:

  ```yaml
  inhibit_rules:
    - source_matchers: ['alertname="HarborMetricsMissing"']
      target_matchers: ['alertname=~"Harbor.*"']
      equal: []
  ```

## What is *not* covered

Harbor's own metrics say nothing about the resources it depends on. Pair these rules with:

- PostgreSQL: [postgres_exporter](https://github.com/prometheus-community/postgres_exporter)
- Redis / Valkey: [redis_exporter](https://github.com/oliver006/redis_exporter)
- Storage backend capacity (PVC, S3/Ceph): kubelet volume metrics, or your object store's metrics
- TLS certificate expiry and external reachability: [blackbox_exporter](https://github.com/prometheus/blackbox_exporter) or cert-manager metrics
- Pod OOMKills / CrashLoops: kube-state-metrics
