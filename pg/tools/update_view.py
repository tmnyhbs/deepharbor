#!/usr/bin/env python3
"""
update_view.py — Compare and apply v_member_info view changes

Reads the view definition from pgsql_schema.sql, compares it against the
live database, shows the differences, and optionally applies the update.
"""

import argparse
import re
import sys
import textwrap


def get_schema_file_view(schema_path):
    """Extract the CREATE OR REPLACE VIEW v_member_info statement from the schema file."""
    with open(schema_path, "r") as f:
        content = f.read()

    # Match from CREATE OR REPLACE VIEW v_member_info through the closing semicolon
    pattern = r"(CREATE OR REPLACE VIEW v_member_info\s+as\s+.+?;)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return match.group(1)


def get_live_view_definition(conn):
    """Get the current view definition from the live database."""
    with conn.cursor() as cur:
        # Check if view exists
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM information_schema.views WHERE table_name = 'v_member_info');"
        )
        exists = cur.fetchone()[0]
        if not exists:
            return None

        cur.execute("SELECT pg_get_viewdef('v_member_info', true);")
        result = cur.fetchone()
        return result[0] if result else None


def extract_fields(view_sql):
    """Extract field names per section from a view definition.

    Returns a dict like:
        {'identity': ['member_id', 'first_name', ...], 'connections': ['discord_username'], ...}
    """
    sections = {}
    # Find all json_build_object sections with their labels
    # Pattern: 'section_name', json_build_object(...)
    # We need to handle nested parentheses for the json_build_object calls

    # First, normalize whitespace for easier parsing
    normalized = " ".join(view_sql.split())

    # Find section labels followed by json_build_object
    section_pattern = r"'(\w+)'\s*,\s*json_build_object\s*\("
    for match in re.finditer(section_pattern, normalized):
        section_name = match.group(1)
        start = match.end()

        # Walk forward counting parens to find the matching close
        depth = 1
        pos = start
        while pos < len(normalized) and depth > 0:
            if normalized[pos] == "(":
                depth += 1
            elif normalized[pos] == ")":
                depth -= 1
            pos += 1

        section_body = normalized[start : pos - 1]

        # Extract field names: 'field_name', <expression>
        field_pattern = r"'(\w+)'\s*,"
        fields = re.findall(field_pattern, section_body)
        sections[section_name] = fields

    return sections


def compare_views(schema_fields, live_fields):
    """Compare field lists between schema file and live DB.

    Returns (added, removed) where each is a dict of section -> [field_names].
    """
    added = {}
    removed = {}

    all_sections = set(list(schema_fields.keys()) + list(live_fields.keys()))
    for section in sorted(all_sections):
        schema_set = set(schema_fields.get(section, []))
        live_set = set(live_fields.get(section, []))

        new_fields = schema_set - live_set
        gone_fields = live_set - schema_set

        if new_fields:
            added[section] = sorted(new_fields)
        if gone_fields:
            removed[section] = sorted(gone_fields)

    # Check for entirely new or removed sections
    new_sections = set(schema_fields.keys()) - set(live_fields.keys())
    gone_sections = set(live_fields.keys()) - set(schema_fields.keys())

    for section in new_sections:
        if section not in added:
            added[section] = sorted(schema_fields[section])

    for section in gone_sections:
        if section not in removed:
            removed[section] = sorted(live_fields[section])

    return added, removed


def print_comparison(schema_fields, live_fields, added, removed):
    """Print a readable comparison of the two view definitions."""
    all_sections = sorted(set(list(schema_fields.keys()) + list(live_fields.keys())))

    for section in all_sections:
        schema_list = schema_fields.get(section, [])
        live_list = live_fields.get(section, [])
        section_added = set(added.get(section, []))
        section_removed = set(removed.get(section, []))

        if not section_added and not section_removed:
            continue

        print(f"\n  [{section}]")
        # Show all fields with markers
        all_fields_ordered = []
        seen = set()
        for f in live_list:
            all_fields_ordered.append(f)
            seen.add(f)
        for f in schema_list:
            if f not in seen:
                all_fields_ordered.append(f)

        for field in all_fields_ordered:
            if field in section_added:
                print(f"    + {field}")
            elif field in section_removed:
                print(f"    - {field}")


def main():
    parser = argparse.ArgumentParser(
        description="Compare and apply v_member_info view changes from schema file to live database."
    )
    parser.add_argument(
        "--host", default="localhost", help="Database host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=5432, help="Database port (default: 5432)"
    )
    parser.add_argument(
        "--dbname", default="deepharbor", help="Database name (default: deepharbor)"
    )
    parser.add_argument(
        "--user", default="dh", help="Database user (default: dh)"
    )
    parser.add_argument(
        "--password", default="dh", help="Database password (default: dh)"
    )
    parser.add_argument(
        "--schema-file",
        default=None,
        help="Path to pgsql_schema.sql (auto-detected from script location)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show differences only, don't prompt or apply",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true", help="Skip confirmation prompt"
    )
    args = parser.parse_args()

    # Try importing psycopg2
    try:
        import psycopg2
    except ImportError:
        print("Error: psycopg2 is required. Install it with:")
        print("  pip install psycopg2-binary")
        sys.exit(1)

    # Resolve schema file path
    if args.schema_file:
        schema_path = args.schema_file
    else:
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.join(script_dir, "..", "sql", "pgsql_schema.sql")

    # Check schema file exists
    import os
    if not os.path.exists(schema_path):
        print(f"Error: Schema file not found at {schema_path}")
        sys.exit(1)

    ### Read view from schema file
    print(f"Reading schema file: {schema_path}")
    schema_view_sql = get_schema_file_view(schema_path)
    if not schema_view_sql:
        print("Error: Could not find CREATE OR REPLACE VIEW v_member_info in schema file")
        sys.exit(1)

    schema_fields = extract_fields(schema_view_sql)
    if not schema_fields:
        print("Error: Could not parse any fields from schema file view definition")
        sys.exit(1)

    ### Connect to database
    print(f"Connecting to {args.user}@{args.host}:{args.port}/{args.dbname}...")
    try:
        conn = psycopg2.connect(
            host=args.host,
            port=args.port,
            dbname=args.dbname,
            user=args.user,
            password=args.password,
        )
        conn.autocommit = True
    except psycopg2.OperationalError as e:
        print(f"Error: Could not connect to database: {e}")
        sys.exit(1)

    ### Read live view
    live_view_sql = get_live_view_definition(conn)
    if live_view_sql is None:
        print("Warning: v_member_info view does not exist in the database.")
        print("The schema file view will be created from scratch.")
        live_fields = {}
    else:
        live_fields = extract_fields(live_view_sql)

    ### Compare
    added, removed = compare_views(schema_fields, live_fields)

    if not added and not removed:
        print("\nNo differences found. The live view matches the schema file.")
        conn.close()
        sys.exit(0)

    ### Show differences
    print("\nDifferences found between schema file and live database:")
    print("  + = in schema file but not in live DB (will be added)")
    print("  - = in live DB but not in schema file (will be removed)")
    print_comparison(schema_fields, live_fields, added, removed)

    total_added = sum(len(v) for v in added.values())
    total_removed = sum(len(v) for v in removed.values())
    print(f"\nSummary: {total_added} field(s) to add, {total_removed} field(s) to remove")

    if args.dry_run:
        print("\n(dry run — no changes applied)")
        conn.close()
        sys.exit(0)

    ### Confirm and apply
    if not args.yes:
        try:
            response = input("\nApply these changes? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            conn.close()
            sys.exit(1)

        if response not in ("y", "yes"):
            print("Aborted.")
            conn.close()
            sys.exit(0)

    ### Apply the view
    print("\nApplying view update...")
    try:
        with conn.cursor() as cur:
            cur.execute(schema_view_sql)
        print("View updated successfully.")
    except Exception as e:
        print(f"Error applying view update: {e}")
        conn.close()
        sys.exit(1)

    ### Verify
    print("\nVerifying...")
    updated_view_sql = get_live_view_definition(conn)
    if updated_view_sql is None:
        print("Warning: Could not read back the updated view.")
    else:
        updated_fields = extract_fields(updated_view_sql)
        verify_added, verify_removed = compare_views(schema_fields, updated_fields)
        if not verify_added and not verify_removed:
            print("Verified: live view now matches the schema file.")
        else:
            print("Warning: View was applied but verification shows remaining differences.")
            print("This may indicate a parsing issue — please check the view manually:")
            print("  psql -h localhost -U dh -d deepharbor -c \"\\d+ v_member_info\"")

    conn.close()


if __name__ == "__main__":
    main()
