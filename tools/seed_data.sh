#!/usr/bin/env bash
#
# seed_data.sh — Manage seed data for the Deep Harbor dev environment
#
# This script provides a convenient way to use either the hand-crafted
# static seed data or the Python generator to populate seed_data.sql.
#
# Usage:
#   tools/seed_data.sh static          Use the hand-crafted seed data (25 members)
#   tools/seed_data.sh generate        Generate random seed data (25 members by default)
#   tools/seed_data.sh generate 100    Generate 110 members (100 random + 10 dev users)
#   tools/seed_data.sh generate 50 abc Generate with specific seed for reproducibility
#   tools/seed_data.sh status          Show what's currently in seed_data.sql
#
# The output file is pg/sql/seed_data.sql, which docker-compose.dev.yml
# mounts as /docker-entrypoint-initdb.d/02-seed_data.sql. After changing
# seed data you'll need to reset the database:
#   docker compose -f docker-compose.yaml -f docker-compose.dev.yml down -v
#   docker compose -f docker-compose.yaml -f docker-compose.dev.yml up --build -d
#

set -euo pipefail

# Figure out the repo root relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SEED_DATA_FILE="$REPO_ROOT/pg/sql/seed_data.sql"
STATIC_SEED_DATA="$REPO_ROOT/pg/sql/seed_data.sql.static"
GENERATOR="$REPO_ROOT/pg/tools/generate_seed_data.py"

usage() {
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  static              Restore the hand-crafted static seed data (25 members)"
    echo "  generate [N] [SEED] Generate seed data with N random members (default: 15)"
    echo "                      plus 10 dev bypass users. Optionally specify a seed"
    echo "                      for reproducibility."
    echo "  status              Show what's currently in seed_data.sql"
    echo ""
    echo "Examples:"
    echo "  $0 static                  Use the committed static seed data"
    echo "  $0 generate                Generate 25 members (15 random + 10 dev)"
    echo "  $0 generate 100            Generate 110 members (100 random + 10 dev)"
    echo "  $0 generate 50 myseed123   Reproducible: same seed = same output"
    echo "  $0 status                  Check current seed data file"
    echo ""
    echo "After changing seed data, reset the database:"
    echo "  docker compose -f docker-compose.yaml -f docker-compose.dev.yml down -v"
    echo "  docker compose -f docker-compose.yaml -f docker-compose.dev.yml up --build -d"
}

cmd_static() {
    # Check if git can restore the committed version
    if git -C "$REPO_ROOT" show HEAD:pg/sql/seed_data.sql > /dev/null 2>&1; then
        git -C "$REPO_ROOT" show HEAD:pg/sql/seed_data.sql > "$SEED_DATA_FILE"
        local count
        count=$(grep -c "INSERT INTO member " "$SEED_DATA_FILE" || true)
        echo "Restored static seed data: $count member inserts"
    else
        echo "Error: No committed seed_data.sql found in git."
        echo "The static seed data file hasn't been committed yet."
        exit 1
    fi
}

cmd_generate() {
    local count="${1:-15}"
    local seed="${2:-}"

    if ! command -v uv &> /dev/null; then
        echo "Error: uv is required to run the generator. Install it:"
        echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi

    local seed_args=()
    if [[ -n "$seed" ]]; then
        seed_args=(--seed "$seed")
    fi

    echo "Generating seed data: $count random + 10 dev users = $((count + 10)) total..."
    uv run "$GENERATOR" --count "$count" "${seed_args[@]}" --output "$SEED_DATA_FILE"
    echo "Wrote $SEED_DATA_FILE"
}

cmd_status() {
    if [[ ! -f "$SEED_DATA_FILE" ]]; then
        echo "No seed data file found at $SEED_DATA_FILE"
        exit 0
    fi

    local member_count role_count
    member_count=$(grep -c "INSERT INTO member (" "$SEED_DATA_FILE" || true)
    role_count=$(grep -c "INSERT INTO member_to_role" "$SEED_DATA_FILE" || true)

    echo "Seed data file: $SEED_DATA_FILE"
    echo "  Members: $member_count"
    echo "  Role assignments: $role_count"

    # Check if it's generated or static
    if head -5 "$SEED_DATA_FILE" | grep -q "generated"; then
        local seed_line
        seed_line=$(grep "Seed:" "$SEED_DATA_FILE" | head -1 || true)
        echo "  Type: Generated"
        echo "  $seed_line"
    else
        echo "  Type: Static (hand-crafted)"
    fi
}

# Main dispatch
case "${1:-}" in
    static)
        cmd_static
        ;;
    generate)
        cmd_generate "${2:-15}" "${3:-}"
        ;;
    status)
        cmd_status
        ;;
    -h|--help|help)
        usage
        ;;
    "")
        usage
        exit 1
        ;;
    *)
        echo "Unknown command: $1"
        echo ""
        usage
        exit 1
        ;;
esac
