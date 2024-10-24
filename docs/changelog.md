# Changelog

### 2024-10-23

- Fixed the wrong dateformat usage in the server uniqueness check.

### 2024-10-21

- Fixed bug with charm upgrade due to wrong ownership of reactive runner log directory.

### 2024-10-18

- Bugfix for logrotate configuration ("nocreate" must be passed explicitly)

### 2024-10-17

- Use in-memory authentication instead of clouds.yaml on disk for OpenStack. This prevents
the multi-processing fighting over the file handle for the clouds.yaml file in the github-runner-manager.

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

- Added support for spawning a runner reactively.
- Fixed a bug where busy runners are killed instead of only idle runners.

### 2024-09-18

- Changed code to be able to spawn a runner in reactive mode.
- Removed reactive mode support for LXD as it is not currently in development.

## 2024-09-09

- Added changelog for tracking user-relevant changes.
