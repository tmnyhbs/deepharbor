# Database Configuration

This directory contains the necessary files and configurations for setting up and managing the PostgreSQL database for the project.
## Contents
- `db-init/init.sql`: SQL script to initialize the database schema and seed initial data.
- `../docker-compose.yaml`: Docker Compose file to set up a PostgreSQL container for development and testing.
- `pg_hba.conf`: PostgreSQL client authentication configuration file.
- `postgresql.conf`: Main PostgreSQL configuration file for tuning database performance.
## Setup Instructions
1. **Using Docker Compose**:
   - Ensure you have Docker and Docker Compose installed on your machine.
   - Navigate to this directory in your terminal.
   - Run the following command to start the PostgreSQL container:
     ```bash
     docker-compose up -d
     ```
    - The database will be accessible at `localhost:5432` with the credentials specified in the `docker-compose.yml` file.
2. **Initializing the Database**:
   - Once the PostgreSQL container is running, you can execute the `init.sql` script to set up the database schema and seed data:
     ```bash
     docker exec -i <container_name> psql -U <username> -d <database_name> -f /path/to/init.sql (in this repository it's `pg/db-init/init.sql`)
     ```
   - Replace `<container_name>`, `<username>`, and `<database_name>` with the appropriate values from your `docker-compose.yml`.
   - The Deep Harbor database schema is located in the `sql/pgsql_schema.sql` file, which contains all the DDL statements needed to create the necessary tables and relationships.
   - Note that if you use the provided `docker-compose.yaml` file in the base diretory everything will be set up automatically including the initialization of the database using the `init.sql` script.
3. **Configuration**:
   - You can modify the `pg_hba.conf` and `postgresql.conf` files to customize authentication methods and performance settings as needed.
   - After making changes to these configuration files, restart the PostgreSQL container to apply the changes:
     ```bash
     docker-compose restart
     ```
## Tools

Database utilities live in `pg/tools/` with shell wrappers in `tools/`.

### update_view — Compare & Apply View Changes

When you add a new field to a JSONB column (e.g., adding `pronouns` to `identity`), the `v_member_info` view in `pg/sql/pgsql_schema.sql` must also be updated to expose it. This tool automates checking and applying those changes.

**Workflow for adding a new field:**
1. Add the field to the portal code (templates, route handlers)
2. Add it to the `v_member_info` view in `pg/sql/pgsql_schema.sql`
3. Run `tools/update_view.sh` to apply the change to the live database

**Usage:**
```bash
# Show what's different between schema file and live DB
tools/update_view.sh --dry-run

# Compare and prompt to apply
tools/update_view.sh

# Apply without prompting
tools/update_view.sh --yes
```

**Database connection** defaults to `dh/dh@localhost:5432/deepharbor`. Override with `--host`, `--port`, `--dbname`, `--user`, `--password`.

### generate_seed_data — Generate Test Data

Generates random member records for dev/testing. Called via `tools/seed_data.sh generate`.

See `tools/seed_data.sh --help` for usage.

## Additional Resources
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker PostgreSQL Image](https://hub.docker.com/_/postgres)