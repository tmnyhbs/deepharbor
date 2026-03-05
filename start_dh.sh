#!/usr/bin/env bash

# This script sets up and starts DeepHarbor, including the PostgreSQL database.
# It assumes Docker and Docker Compose are installed on the system.

# Set up the git version string from the current commit
export GIT_VERSION="$(git branch --show-current)-$(git rev-parse --short HEAD) $(date +%Y-%m-%d)"

# Create a Docker network for DeepHarbor
docker network create dh_network

# Now start the services using Docker Compose
docker compose up -d