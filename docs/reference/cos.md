# COS Integration

## Metrics

### Runner and Charm Insights
Upon [COS](https://charmhub.io/topics/canonical-observability-stack) integration, this charm initiates the transmission of various metrics—refer to the relevant [specification](https://discourse.charmhub.io/t/specification-isd075-github-runner-cos-integration/12084) for comprehensive details—regarding the runner instances and the charm itself.

There are two dashboards. One for fine-granular metrics, called "GitHub Self-Hosted Runner Metrics", and one for long-term metrics,
called "GitHub Self-Hosted Runner Metrics (Long-Term)". 

The "GitHub Self-Hosted Runner Metrics" metrics dashboard presents the following rows:

- General: Displays general metrics about the charm and runners, such as:
  - Share of jobs per application: A pie chart showing the share of jobs per application.
  - Lifecycle counters: Tracks the frequency of Runner initialisation, start, stop, and crash events.
  - Available runners: A horizontal bar graph showing the number of runners available (and max expected) during the last reconciliation event. Note: This data is updated after each reconciliation event and is not real-time. 
  - Runners after reconciliation: A time series graph showing the number of runners marked as active/idle, the number of expected runners, and the difference between expected and the former (unknown) during the last reconciliation event over time. Note: This data is updated after each reconciliation event and is not real-time.
  - Duration observations: Each data point aggregates the last hour and shows the 50th, 90th, 95th percentile and maximum durations for:
      - Runner installation
      - Runner idle duration
      - Charm reconciliation duration
      - Job queue duration - how long a job waits in the queue before a runner picks it up
  - Max job queue duration by application: Similar to "Job queue duration" panel, but shows maximum durations by charm application.
  - Average reconciliation interval: Shows the average time between reconciliation events, broken down by charm application.
- Jobs: Displays certain metrics about the jobs executed by the runners. These metrics can be displayed per repository by specifying a
 regular expression on the `Repository` variable. The following metrics are displayed:
  - Proportion charts: Share of jobs by completion status, job conclusion, application, repo policy check failure http codes and github events over time.
  - Job duration observation
  - Number of jobs per repository

The "GitHub Self-Hosted Runner Metrics (Long-Term)" metrics dashboard displays the following rows:

- General: Contains the following panels:
  - Total Jobs
  - Runners created per application: Shows the number of runners created per charm application.
  - Total unique repositories
  - Timeseries chart displaying the number of jobs per day
  - Percentage of jobs with low queue time (less than 60 seconds)

Both dashboards allow for filtering by charm application by specifying a regular expression on the `Application` variable.


While the dashboard visualises a subset of potential metrics, these metrics are logged in a file named `/var/log/github-runner-metrics.log`. Use following Loki query to retrieve lines from this file:

```
{filename="/var/log/github-runner-metrics.log"}
```

These log events contain valuable details such as charm application, GitHub events triggering workflows along with their respective repositories, and more. Customising metric visualisation is possible to suit specific needs.

### Machine Host Metrics
The `grafana-agent` autonomously transmits machine host metrics, which are visualised in the `System Resources` dashboard.

## Logs

The `grafana-agent` effectively transmits all logs located at `/var/log/**/*log`, from the charm unit to Loki. Additionally, it collects logs concerning crashed runners with accessible but unshut LXD virtual machines.


## Alerts

The charm contains a number of alerts that are sent to COS using the `grafana-agent`. 
Please refer to the COS documentation for more information on how to set up alerts.

Alerts are divided into two categories: 

- Capacity Alerts: Alerts you when there is a shortage of a particular type of runner.
- Failure Alerts: Notification of runner crashes or repo policy related failures.