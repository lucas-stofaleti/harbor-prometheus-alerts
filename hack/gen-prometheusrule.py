#!/usr/bin/env python3
"""Generate kubernetes/prometheusrule.yaml (Prometheus Operator CRD) from
rules/harbor-alerts.yaml so the two never drift apart.

Usage: python3 hack/gen-prometheusrule.py [--name NAME] [--namespace NS]
Requires: PyYAML
"""
import argparse
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent


class Literal(str):
    """Marker so multi-line strings are emitted as YAML block scalars."""


def literal_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style="|")


yaml.add_representer(Literal, literal_representer)


def mark_multiline(node):
    if isinstance(node, dict):
        return {k: mark_multiline(v) for k, v in node.items()}
    if isinstance(node, list):
        return [mark_multiline(v) for v in node]
    if isinstance(node, str) and "\n" in node:
        return Literal(node)
    return node


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="harbor-alerts")
    parser.add_argument("--namespace", default=None)
    parser.add_argument("--rules", default=str(ROOT / "rules" / "harbor-alerts.yaml"))
    parser.add_argument("--out", default=str(ROOT / "kubernetes" / "prometheusrule.yaml"))
    args = parser.parse_args()

    groups = yaml.safe_load(pathlib.Path(args.rules).read_text())["groups"]

    metadata = {
        "name": args.name,
        "labels": {
            "app.kubernetes.io/name": "harbor-alerts",
            # kube-prometheus-stack only picks up rules whose labels match its
            # ruleSelector (by default: release=<helm release name>). Add it here
            # or via `kubectl label` if your rules are not being loaded.
            # "release": "kube-prometheus-stack",
        },
    }
    if args.namespace:
        metadata["namespace"] = args.namespace

    doc = {
        "apiVersion": "monitoring.coreos.com/v1",
        "kind": "PrometheusRule",
        "metadata": metadata,
        "spec": {"groups": mark_multiline(groups)},
    }

    header = (
        "# GENERATED FILE - do not edit by hand.\n"
        "# Source: rules/harbor-alerts.yaml  (regenerate with `make prometheusrule`)\n"
        "# NOTE: annotations contain Go templates ({{ ... }}). If you embed this file\n"
        "# in a Helm chart, escape them, e.g. {{ \"{{ $labels.job }}\" }}.\n"
    )
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(header + yaml.dump(doc, sort_keys=False, width=1000000, default_flow_style=False))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
