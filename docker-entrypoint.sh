#!/bin/sh
set -e
flask db upgrade

# Bring datasets and their fields up to date with the specification. This is
# maintenance rather than part of serving, so a specification or GitHub outage
# must not stop the application starting: log the failure and carry on.
flask data new-datasets || echo "WARNING: flask data new-datasets failed"
flask data dataset-fields || echo "WARNING: flask data dataset-fields failed"

flask run --debug
