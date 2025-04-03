#!/bin/bash
# Create temporary Gremlin init script
cat > gremlin-init.groovy << EOF
// Connect to the remote server
:remote connect tinkerpop.server conf/remote.yaml
// Switch to remote console mode
:remote console
EOF

# Run Docker with the script in interactive mode
docker compose -f docker-compose-cql-es.yml run --rm \
-e GREMLIN_REMOTE_HOSTS=janusgraph \
-v $(pwd)/gremlin-init.groovy:/opt/janusgraph/gremlin-init.groovy \
janusgraph ./bin/gremlin.sh -i /opt/janusgraph/gremlin-init.groovy

# Clean up
rm gremlin-init.groovy