#!/usr/bin/env bash
#
# update_view.sh — Compare and apply v_member_info view changes
#
# Compares the view definition in pg/sql/pgsql_schema.sql against the
# live database, shows what's new or removed, and optionally applies
# the update.
#
# Usage:
#   tools/update_view.sh              Compare and prompt to apply
#   tools/update_view.sh --dry-run    Show differences only
#   tools/update_view.sh --yes        Apply without prompting
#
# Database connection defaults to localhost:5432/deepharbor (dh/dh).
# Override with --host, --port, --dbname, --user, --password.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TOOL="$REPO_ROOT/pg/tools/update_view.py"

usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Compare the v_member_info view in pg/sql/pgsql_schema.sql against"
    echo "the live database and optionally apply changes."
    echo ""
    echo "Options:"
    echo "  --dry-run           Show differences only, don't apply"
    echo "  --yes, -y           Skip confirmation prompt"
    echo "  --host HOST         Database host (default: localhost)"
    echo "  --port PORT         Database port (default: 5432)"
    echo "  --dbname NAME       Database name (default: deepharbor)"
    echo "  --user USER         Database user (default: dh)"
    echo "  --password PASS     Database password (default: dh)"
    echo "  -h, --help          Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                  Compare and prompt to apply"
    echo "  $0 --dry-run        Just show what's different"
    echo "  $0 --yes            Apply without asking"
}

# Show help if requested
for arg in "$@"; do
    if [[ "$arg" == "-h" || "$arg" == "--help" || "$arg" == "help" ]]; then
        usage
        exit 0
    fi
done

# Check uv is available (handles psycopg2-binary dependency automatically)
if ! command -v uv &> /dev/null; then
    echo "Error: uv is required. Install it:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check the tool script exists
if [[ ! -f "$TOOL" ]]; then
    echo "Error: update_view.py not found at $TOOL"
    exit 1
fi

# Run with psycopg2-binary provided automatically by uv
uv run --with psycopg2-binary "$TOOL" "$@"
