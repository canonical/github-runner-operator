#!/bin/bash

unit="$1"
event="$2"
timeout="$3"

flock -n -E 0 "/run/github-runner-operator/$event" -- juju-run "$unit" "JUJU_DISPATCH_PATH=$event timeout $timeout ./dispatch"
