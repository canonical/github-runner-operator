---
title: ADR-001 - Pressure reconciler design for planner integration
author: Christopher Bartz (christopher.bartz@canonical.com)
date: 2026/02/20
domain: architecture
replaced-by: 
---

## Overview

This ADR documents the design of the `PressureReconciler`, which enables the
github-runner-manager to scale runners on demand in response to pressure signals
from the planner service, while preserving the existing timer-based reconciliation
for deployments without a planner.

## Context

The runner manager historically determined the desired runner count in two ways:
a static count from configuration (number of VMs for each combination), or on demand
by consuming job messages from a MongoDB queue. With the introduction of the planner
charm, the desired runner count becomes a dynamic value driven by observed queue
depth—referred to as *pressure*. The runner manager must respond to pressure changes
quickly (to prevent queued jobs from waiting) while also periodically cleaning up
stale runners.

Two competing concerns shape the design:

- **Low-latency scale-up**: runners should be created as soon as the planner signals
  increased demand, not on a fixed reconcile tick.
- **Periodic cleanup**: stale runners (e.g. completed jobs whose VM was not yet
  reclaimed) must be removed on a regular schedule regardless of inbound pressure.

## Decision

The `PressureReconciler` runs two independent, long-lived loops that share a mutex
with the existing reconcile path:

1. **Create loop** – streams pressure from the planner and creates runners
   whenever the desired total exceeds the current count. Tracks runner count
   in memory to avoid expensive OpenStack/GitHub API calls on every event.

2. **Reconcile loop** – wakes on a configurable timer, cleans up stale runners,
   syncs the in-memory count with reality, and scales up if needed. Does not
   actively scale down — excess healthy runners drain naturally through cleanup.

Planner mode is activated only when `planner_url` and `planner_token` are present
in configuration, allowing staged rollout before the legacy reconcile path is
removed.

When the streaming connection fails, the create loop falls back to
`fallback_runners` (configurable, default zero) and retries after a short backoff,
preventing a hot loop on transient planner outages.

## Alternatives explored

**A single unified reconcile loop.** Combining create and delete into one loop
simplifies concurrency but forces a trade-off: either the loop runs frequently
(introducing excessive GitHub and OpenStack API calls) or it runs infrequently
(losing the low-latency create behaviour). Cleanup involves listing runners through
the GitHub API and querying OpenStack for VM state — calls that are expensive both
in latency and in quota. GitHub rate limiting has caused operational problems for
this project in the past, and OpenStack also degrades under high call rates.
Separate loops let creates react in near-real-time while keeping API call volume
proportional to the configured cleanup interval.

**Fetching fresh pressure in the reconcile loop.** Having the reconcile loop call
`GET /api/v1/flavors/{name}/pressure` itself would give it an up-to-date reading.
However, this adds an extra network round-trip on every timer tick, couples the
reconcile loop to planner availability, and is unnecessary because any over-deletion
caused by a stale reading is self-correcting: the create loop will scale back up
on the next streaming event.

## Tradeoffs

- The reconcile loop uses the last pressure seen by the create loop, not a live
  reading. Staleness is bounded by the stream update frequency.
- The in-memory runner count can drift from reality (e.g. VMs that fail after
  creation). This acts as a natural backoff — no further creates until the
  reconcile loop syncs. The reconcile loop corrects drift on every tick.
- Excess healthy runners are not forcibly killed. They drain through cleanup,
  which avoids killing in-flight jobs but may temporarily exceed the desired
  count.
