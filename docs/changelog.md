# Changelog

This changelog documents user-relevant changes to the GitHub runner charm.

## 2025-08-19

- Updated the documentation workflow to be fully integrated with the Vale GitHub Action.

## 2025-08-12

- Metrics are now issued even without runner installed timestamp.

## 2025-07-28

- Fix an issue where the charm can error out due to timeout during flush runners.

## 2025-07-24

- Fix an issue with infinite retry of a reactive job message.

## 2025-07-22

- Removed support for using both jobmanager and GitHub at the same time.


## 2025-07-18

- Fix an issue where flushing runners does not include reactive processes. This cause some reactive runner to spawn with old code after upgrade.

## 2025-07-16

- Split the `reconcile_duration` buckets for Prometheus metrics into a larger bucket set.
- Fix the incorrect default value of the aproxy-exclude-addresses configuration.

## 2025-07-09

- Specify max supported nova compute API to be 2.91. This fixes an issue where the charm could fail
 due to a bug on the OpenStack side: https://bugs.launchpad.net/nova/+bug/2095364

### 2025-06-30

- New configuration options aproxy-exclude-addresses and aproxy-redirect-ports for allowing aproxy to redirect arbitrary TCP traffic
- Added prometheus metrics to the GitHub runner manager application.

## 2025-06-26

- Fix a process leak internal to the charm.

- Fix a bug where deleted GitHub Actions Job would cause an endless loop of retries.

### 2025-06-17

- Fix a bug where SSH connection error always appears in the logs.

### 2025-06-16

- Revert `copytruncate logrotate` method for reactive processes, as `copytruncate` keeps log files on disks and does not remove them, and each process is writing to a new file leading to a huge and increasing amount
of zero sized files in the reactive log directory. This is a temporary fix until a better solution is implemented, as it has the downside that long lived reactive processes may write to deleted log files.


### 2025-06-12

- Disable and remove any legacy service on upgrade. This fixes issue with the legacy service in upgraded units.

### 2025-06-10

- Fix issue with upgraded charm unit unable to issue metrics due to metric log ownership issues.

### 2025-06-04

- Reduce the reconcile-interval configuration from 10 minutes to 5 minutes. This is the interval 
between reconciling the current and intended number of runners. The value should be kept low, 
unless GitHub API rate limiting is encountered.
- Removed the reconcile-runners Juju action.

### 2025-06-03

- Redirect HKP protocol traffic (port 11371) to aproxy

### 2025-05-22

- Add possibility to run a script in the pre-job phase of a runner. This can be useful to setup 
network/infrastructure specific things.


### 2025-05-09

- The log rotation is done by copying the logs then truncating. There is a small chance some log might be lost during the log rotation. This affects the github-runner-manager service logs, and the reactive spawning logs.

### 2025-05-06

- The ssh health checks are removed and GitHub is used instead to get the runners health
information. This implies many changes in both the structure of the project and its functionality. Potentially, many race conditions should
disappear.

### 2025-04-28

- Add a visualization of the share of jobs started per application.

### 2025-04-22

- Add how-to landing page.

### 2025-04-15

- Fix a race condition where key pairs were being deleted even though the server was being built, potentially killing active GitHub action runs.

### 2025-04-09

- Remove update-dependencies action. This actions is not needed for external cloud providers.

### 2025-03-27

- Add proxy configuration options for charm to facilitate its use in corporate environments.
  - manager-ssh-proxy-command: ProxyCommand ssh-config option used to ssh from the manager to the runners.
  - runner-http-proxy: Allows the proxy in the runner to be different to the proxy in the
    Juju model config for the manager.
  - use-runner-proxy-for-tmate: Whether to proxy the ssh connection from the runner to the tmate-server
    using the runner http proxy.

### 2025-03-25

- Add documentation explaining security design of the charm.

### 2025-03-24

- New terraform product module. This module is composed of one github-runner-image-builder application and the related
github-runner applications.

### 2024-12-13

- Add the difference between expected and actual runners to the "Runners after reconciliation" dashboard panel.

### 2024-12-05

- Bug fix to no longer stop the reconciliation when a runner's health check fails.

### 2024-12-04

- Clean up corresponding OpenStack runner resources when a unit of the charm is removed.

### 2024-11-27

- Fix "Available Runners" dashboard panel to work for multiple flavors.

### 2024-11-15

- Catch ReconcileError and set appropriate message in unit status.

### 2024-11-13

- Added documentation for the reactive mode (how-to and mongodb integration references).
- Align the README with the one in https://github.com/canonical/is-charms-template-repo.

### 2024-10-24

- Add `expected_runners` to reconciliation metric.

### 2024-10-23

- Fixed the wrong `dateformat` usage in the server uniqueness check.

### 2024-10-21

- Fixed bug with charm upgrade due to wrong ownership of reactive runner log directory.

### 2024-10-18

- Bug fix for `logrotate` configuration (`nocreate` must be passed explicitly)

### 2024-10-17

- Use in-memory authentication instead of clouds.yaml on disk for OpenStack. This prevents
the multi-processing fighting over the file handle for the clouds.yaml file in the `github-runner-manager`.

- Fixed a bug where metrics storage for unmatched runners could not get cleaned up.

### 2024-10-11

- Added support for COS integration with reactive runners.
- The charm now creates a dedicated user which is used for running the reactive process and 
  storing metrics and ssh keys (also for non-reactive mode).

### 2024-10-07

- Fixed the removal of proxy vars in `.env` file for LXD runners.
- Fixed a regression in the removal of leftover directories.
- Improved reconciliation for reactive runners.

### 2024-09-27

- Added job label validation when consuming a job from the message queue.

### 2024-09-24

- Added support for spawning a reactive runner.
- Fixed a bug where busy runners are killed instead of only idle runners.

### 2024-09-18

- Changed code to be able to spawn a runner in reactive mode.
- Removed reactive mode support for LXD as it is not currently in development.

## 2024-09-09

- Added changelog for tracking user-relevant changes.