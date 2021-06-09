#!/usr/bin/env bash

PORT=8123

curl -kLs --fail --max-time 10 https://localhost:${PORT}
