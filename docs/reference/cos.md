# COS Integration

## Metrics

### Runner and Charm Insights
Upon [COS](https://charmhub.io/topics/canonical-observability-stack) integration, this charm initiates the transmission of various metrics—refer to the relevant [specification](https://discourse.charmhub.io/t/specification-isd075-github-runner-cos-integration/12084) for comprehensive details—regarding the runner instances and the charm itself.

The dashboard presents the following rows:

- General: Displays general metrics about the charm and runners, such as:
  - Lifecycle counters: Tracks the frequency of Runner initialisation, start, stop, and crash events.
  - Idle runners after reconciliation: Reflects the count of Runners marked as idle during the last reconciliation event. Note: This data updates post-reconciliation events and isn't real-time.
  - Duration observations: Each data point aggregates the last hour, showcasing minimum, maximum, and average durations for:
      - Runner installation
      - Runner idle duration
      - Charm reconciliation duration
      - Job queue duration - how long a job waits in the queue before a runner picks it up
- Jobs: Displays certain metrics about the jobs executed by the runners. These metrics can be displayed per repository by specifying a
 regular expression on the `Repository` variable. The following metrics are displayed:
  - Pie charts: Share of jobs by completion status, job conclusion, flavor, repo policy check failure http codes and github events.
  - Job duration observation
  - Number of jobs per repository



While the dashboard visualises a subset of potential metrics, these metrics are logged in a file named `/var/log/github-runner-metrics.log`. Use following Loki query to retrieve lines from this file:

```
{filename="/var/log/github-runner-metrics.log"}
```

These log events contain valuable details such as flavor (pertinent for multiple runner applications), GitHub events triggering workflows along with their respective repositories, and more. Customising metric visualisation is possible to suit specific needs.

### Machine Host Metrics
The `grafana-agent` autonomously transmits machine host metrics, which are visualised in the `System Resources` dashboard.

## Logs

The `grafana-agent` effectively transmits all logs located at `/var/log/**/*log`, from the charm unit to Loki. Additionally, it collects logs concerning crashed runners with accessible but unshut LXD virtual machines.