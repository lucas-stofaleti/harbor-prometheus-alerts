# Harbor Prometheus Alerts

[![CI](https://github.com/lucas-stofaleti/harbor-prometheus-alerts/actions/workflows/ci.yml/badge.svg)](https://github.com/lucas-stofaleti/harbor-prometheus-alerts/actions/workflows/ci.yml)

A small, tested set of [Prometheus](https://prometheus.io) alerting rules for [Harbor](https://goharbor.io), the CNCF container registry. Copy the whole file, copy a single alert, or use it as a starting point for your own rules.

This is a community project and is not part of the official Harbor project.

- **7 alerts** that watch symptoms (is Harbor reachable, are requests failing, are pulls slow, is work stuck) instead of every internal counter.
- A plain Prometheus rules file and a generated Prometheus Operator `PrometheusRule`.
- Unit-tested with `promtool` in CI.
- Metric and label names checked against Harbor 2.15 running in Kubernetes (the [harbor-helm](https://github.com/goharbor/harbor-helm) chart, scraped by kube-prometheus-stack).
- Honest about what it cannot see. See [What is not covered](#what-is-not-covered).

> Every threshold is a sensible starting point, not a universal truth. Tune them to your traffic.

## Quick start

### 1. Make sure Harbor metrics are scraped

With the Helm chart:

```yaml
# values.yaml for the harbor chart
metrics:
  enabled: true
  serviceMonitor:
    enabled: true
    additionalLabels:
      release: kube-prometheus-stack   # must match your Prometheus ruleSelector
```

With docker-compose or a static scrape config, enable metrics in `harbor.yml` and follow the [official metrics docs](https://goharbor.io/docs/latest/administration/metrics/#scraping-metrics-with-prometheus).

Two things the rules depend on:

- **Scrape job names.** `HarborTargetDown` looks at `up{job=~".*harbor.*"}`. That matches the chart's ServiceMonitor (`job="harbor"`) and the job names in the Harbor docs (`harbor-core`, `harbor-registry`, ...). Change the matcher if yours differ.
- **The `component` label.** The health alerts use the `component` label that the exporter puts on `harbor_up`. The chart's ServiceMonitor sets `honorLabels: true`, which keeps it. With `honor_labels: false`, Prometheus renames a label that clashes with a target label to `exported_component`, and the component alerts would silently match nothing. Check with `harbor_up` in the Prometheus UI.

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

`kubernetes/prometheusrule.yaml` is generated from `rules/harbor-alerts.yaml`. Do not edit it by hand (see [Contributing](#contributing)).

## Alerts

| Alert | Severity | For | Fires when |
|---|---|---|---|
| `HarborTargetDown` | critical | 5m | Every scrape target of a job/service is down. Also catches a dead exporter, which would silently disable the health, queue and quota alerts. |
| `HarborComponentUnhealthy` | critical | 5m | Harbor's health check reports `core`, `database`, `redis` or `registry` as unhealthy. These are on the push/pull path. |
| `HarborAuxiliaryComponentUnhealthy` | warning | 15m | Any other component (`jobservice`, `portal`, `registryctl`, `trivy`, or one added later) is unhealthy. Push and pull keep working, but a feature is degraded. |
| `HarborErrorRateHigh` | critical | 10m | More than 5% of client requests served by core return 5xx. Core also proxies all `/v2` registry traffic, so this is the user-facing symptom. |
| `HarborManifestLatencyHigh` | warning | 10m | The p90 of manifest GET/HEAD requests is above 2s on the slowest core replica. Every pull starts with these calls. |
| `HarborJobQueueStalled` | warning | 15m | The oldest queued job of a type has waited over 30 minutes **and** the queue has not shrunk in 30 minutes. |
| `HarborProjectQuotaNearlyFull` | warning | 15m | A project with a quota has used more than 90% of it. Projects without a quota are ignored. |

**Severity.** `critical`: push/pull is failing or about to fail, page someone. `warning`: a feature is degraded or a limit is approaching, open a ticket or send a chat message.

### Notes on specific alerts

- **`HarborErrorRateHigh`** ignores the probe-style requests (`GetPing`, `GetHealth`, `GetSystemInfo`) so a stream of healthy checks cannot hide real failures on a quiet instance. The operation names are matched case-insensitively. It has no minimum-traffic guard on purpose, so a low-volume client that fails every request still alerts.
- **`HarborManifestLatencyHigh`** uses manifests because they are small and their latency does not depend on image size, unlike blobs. Manifest `PUT` is excluded. The metric is a summary, which cannot be aggregated across replicas, so the alert uses the slowest one. On a very quiet instance a single slow request can hold the p90 up for the length of the summary window.

### Design

- **Few alerts, each on a symptom.** Fewer rules are easier to tune, trust and maintain.
- **Replica-safe.** Rules aggregate with `without (instance, pod)`. Replicas collapse into one series, and labels such as `namespace`, `service` and your own `cluster` or tenant labels survive for Alertmanager routing and grouping.
- **Every alert has a unit test**, and the tests include the edge cases that mattered in practice (see `tests/harbor-alerts.test.yaml`).

## What is not covered

Metrics only tell part of the story. Know these limits before relying on the rules.

- **Failed jobs are not covered.** Scans, garbage collection and replication failures have no alert. Job counters depend too much on how often each job runs to alert on reliably, and replication failures such as an expired credential may not appear in them at all. Use [Harbor's webhooks](https://goharbor.io/docs/latest/working-with-projects/project-configuration/configure-webhooks/) for these, or poll the Harbor API.
- **Proxy-cache upstream failures mostly return 404, not 5xx.** In testing on Harbor 2.15, with the upstream returning 401, returning 500, or down: cached content kept being served, an uncached manifest returned **404**, and an uncached blob returned 401 or 500. So `HarborErrorRateHigh` stays silent for most of them. The health of each registry endpoint does not appear among the Harbor metrics we checked. Polling `GET /api/v2.0/registries`, which reports each endpoint's `status`, is the way to catch it.

## Contributing

Issues and pull requests are welcome. A new alert should:

1. Alert on a **symptom** someone would act on.
2. Be **checked against a real Harbor**. Say which version, and show that the metric and label names exist.
3. Have a **unit test** that covers the firing case and at least one case where it must stay silent.
4. Say what it **cannot** see.

Tooling:

```bash
make lint                # promtool check rules
make test                # promtool unit tests
make prometheusrule      # regenerate kubernetes/prometheusrule.yaml from the rules
make check-generated     # what CI runs: fails if the generated file is out of date
```

CI uses [promtool](https://prometheus.io/docs/prometheus/latest/command-line/promtool/) and PyYAML. After changing `rules/harbor-alerts.yaml`, run `make prometheusrule` and commit the result, and update the table in this README.
