PROMTOOL ?= promtool

.PHONY: all lint test prometheusrule check-generated

all: lint test

## Syntax + best-practice checks of the rules
lint:
	$(PROMTOOL) check rules rules/harbor-alerts.yaml

## Unit tests (promtool)
test:
	$(PROMTOOL) test rules tests/harbor-alerts.test.yaml

## Regenerate the Prometheus Operator PrometheusRule from the plain rules file
prometheusrule:
	python3 hack/gen-prometheusrule.py

## Fails in CI if kubernetes/prometheusrule.yaml is out of date
check-generated: prometheusrule
	git diff --exit-code kubernetes/prometheusrule.yaml
