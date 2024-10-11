# Changelog
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
