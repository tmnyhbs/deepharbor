# Deep Harbor ← Purple Asset One: Equipment Module Merge Plan (Final)

**Baselined against:** Deep Harbor `dev` branch (commit `0cdb46d`) and Purple Asset One `main` (commit `dcc0c70`)

---

## Phase 0: Pre-Decisions

### 0.1 — Primary Key Strategy

All new equipment tables use `INTEGER GENERATED ALWAYS AS IDENTITY`, matching DH's existing `member` table pattern. This means PA1's backend code must be rewritten during porting — every query, endpoint, and frontend reference currently works with UUID strings and needs conversion to integers.

### 0.2 — File Storage

RustFS replaces MinIO as the S3-compatible object storage layer. RustFS is Apache 2.0 licensed, S3-compatible, and a drop-in replacement at the application level — PA1's `boto3` client code doesn't change, just the container it points to. Environment variables change from `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` to `RUSTFS_ACCESS_KEY` / `RUSTFS_SECRET_KEY`.

Note: RustFS is currently in alpha. Acceptable for DH's timeline.

### 0.3 — Branch Strategy

Work from a personal fork. Working branch on the fork, then PR to `pumpingstationone/deepharbor` `dev` when ready.

---

## Phase 1: Database Schema Changes

All additions append to the existing `pgsql_schema.sql` (currently 1,437 lines on `dev`). No new extensions are required — double-booking for schedules is handled at the application layer.

### 1.1 — New Roles

Two new roles added to the existing `roles` table, continuing from the current highest ID of 6. Both use the `namespace.key` permission convention already in use on dev:

```sql
INSERT INTO roles (id, name, permission) OVERRIDING SYSTEM VALUE VALUES (
    7, 'Area Host',
    '{
        "view": [
            "member.identity", "member.authorizations", "member.notes",
            "equipment.areas", "equipment.items", "equipment.groups",
            "equipment.tickets", "equipment.schedules", "equipment.auth_sessions",
            "equipment.maintenance", "equipment.dashboard"
        ],
        "change": [
            "member.authorizations", "member.notes",
            "equipment.areas", "equipment.items", "equipment.groups",
            "equipment.tickets", "equipment.schedules", "equipment.auth_sessions",
            "equipment.maintenance"
        ]
    }'
);

INSERT INTO roles (id, name, permission) OVERRIDING SYSTEM VALUE VALUES (
    8, 'Technician',
    '{
        "view": [
            "member.identity", "member.authorizations", "member.notes",
            "equipment.areas", "equipment.items", "equipment.groups",
            "equipment.tickets", "equipment.schedules", "equipment.auth_sessions",
            "equipment.maintenance", "equipment.dashboard"
        ],
        "change": [
            "member.notes",
            "equipment.items", "equipment.tickets",
            "equipment.schedules", "equipment.maintenance"
        ]
    }'
);

SELECT setval(pg_get_serial_sequence('roles', 'id'), (SELECT MAX(id) FROM roles));
```

### 1.2 — New Tables

All tables use `INTEGER GENERATED ALWAYS AS IDENTITY` for primary keys. Foreign keys referencing people are `INTEGER REFERENCES member(id)`.

**1.2.1 — Areas**

```sql
CREATE TABLE IF NOT EXISTS areas (
    id          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name        TEXT UNIQUE NOT NULL,
    description TEXT,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

Named simply `areas` for future reuse beyond equipment.

**1.2.2 — Equipment**

```sql
CREATE TABLE IF NOT EXISTS equipment (
    id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    area_id         INTEGER REFERENCES areas(id) ON DELETE SET NULL,
    common_name     TEXT,
    make            TEXT NOT NULL,
    model           TEXT NOT NULL,
    serial_number   TEXT UNIQUE NOT NULL,
    build_date      DATE,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','inactive','under_repair','decommissioned')),
    schedulable     BOOLEAN DEFAULT FALSE,
    electrical      JSONB DEFAULT '{}',
    breaker         JSONB DEFAULT '{}',
    attributes      JSONB DEFAULT '{}',
    attachments     JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    version         INTEGER DEFAULT 1
);
CREATE INDEX idx_equipment_area ON equipment(area_id);
CREATE INDEX idx_equipment_status ON equipment(status);
CREATE INDEX idx_equipment_attributes ON equipment USING GIN(attributes);
```

The `electrical` column stores structured power specs:
```json
{
    "voltage": 240,
    "amperage": 30,
    "phase": "single",
    "plug_type": "NEMA 6-30P",
    "notes": "Requires dedicated circuit"
}
```

The `breaker` column stores circuit location:
```json
{
    "panel": "B",
    "breaker_number": 14,
    "location_description": "North wall, behind the CNC area",
    "notes": "Shared circuit with dust collector"
}
```

**1.2.3 — Equipment Groups**

```sql
CREATE TABLE IF NOT EXISTS equipment_groups (
    id          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name        TEXT NOT NULL,
    description TEXT,
    area_id     INTEGER REFERENCES areas(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS equipment_group_members (
    group_id     INTEGER NOT NULL REFERENCES equipment_groups(id) ON DELETE CASCADE,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    sort_order   INTEGER DEFAULT 0,
    PRIMARY KEY (group_id, equipment_id)
);
```

**1.2.4 — Repair Tickets**

```sql
CREATE SEQUENCE IF NOT EXISTS ticket_seq START 1000;

CREATE OR REPLACE FUNCTION next_ticket_number()
RETURNS TEXT AS $$
BEGIN
    RETURN 'TKT-' || LPAD(nextval('ticket_seq')::TEXT, 6, '0');
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS repair_tickets (
    id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    equipment_id    INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    ticket_number   TEXT UNIQUE NOT NULL DEFAULT next_ticket_number(),
    opened_by       INTEGER REFERENCES member(id),
    assigned_to     INTEGER REFERENCES member(id),
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','in_progress','on_hold','closed')),
    priority        TEXT NOT NULL DEFAULT 'normal'
                    CHECK (priority IN ('low','normal','high','critical')),
    title           TEXT NOT NULL,
    description     TEXT,
    opened_at       TIMESTAMPTZ DEFAULT NOW(),
    closed_at       TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    work_log        JSONB DEFAULT '[]',
    parts_used      JSONB DEFAULT '[]',
    attachments     JSONB DEFAULT '[]',
    metadata        JSONB DEFAULT '{}',
    category        TEXT NOT NULL DEFAULT 'repair'
                    CHECK (category IN ('repair','maintenance')),
    version         INTEGER DEFAULT 1
);
CREATE INDEX idx_tickets_equipment ON repair_tickets(equipment_id);
CREATE INDEX idx_tickets_status ON repair_tickets(status);
CREATE INDEX idx_tickets_assigned ON repair_tickets(assigned_to);
```

**1.2.5 — Maintenance Schedules & Events**

```sql
CREATE TABLE IF NOT EXISTS maintenance_schedules (
    id                  INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    title               TEXT NOT NULL,
    description         TEXT,
    equipment_id        INTEGER REFERENCES equipment(id) ON DELETE CASCADE,
    group_id            INTEGER REFERENCES equipment_groups(id) ON DELETE CASCADE,
    recurrence_type     TEXT NOT NULL DEFAULT 'days'
                        CHECK (recurrence_type IN ('days','weeks','months','years')),
    recurrence_interval INTEGER NOT NULL DEFAULT 30,
    assigned_to         INTEGER REFERENCES member(id) ON DELETE SET NULL,
    created_by          INTEGER NOT NULL REFERENCES member(id) ON DELETE CASCADE,
    priority            TEXT NOT NULL DEFAULT 'normal'
                        CHECK (priority IN ('low','normal','high','critical')),
    estimated_minutes   INTEGER,
    checklist           JSONB DEFAULT '[]',
    notify_roles        TEXT[] DEFAULT '{}',
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT maint_sched_target CHECK (equipment_id IS NOT NULL OR group_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS maintenance_events (
    id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    schedule_id     INTEGER NOT NULL REFERENCES maintenance_schedules(id) ON DELETE CASCADE,
    equipment_id    INTEGER REFERENCES equipment(id) ON DELETE CASCADE,
    due_date        TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','in_progress','completed','skipped','overdue')),
    assigned_to     INTEGER REFERENCES member(id) ON DELETE SET NULL,
    completed_by    INTEGER REFERENCES member(id) ON DELETE SET NULL,
    completed_at    TIMESTAMPTZ,
    notes           TEXT,
    checklist_state JSONB DEFAULT '[]',
    ticket_id       INTEGER REFERENCES repair_tickets(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_maint_events_due ON maintenance_events(due_date);
CREATE INDEX idx_maint_events_status ON maintenance_events(status);
```

**1.2.6 — Equipment Use Schedules**

```sql
CREATE TABLE IF NOT EXISTS equipment_schedules (
    id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    equipment_id    INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    member_id       INTEGER NOT NULL REFERENCES member(id) ON DELETE CASCADE,
    title           TEXT,
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ NOT NULL,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_equip_schedules_equipment ON equipment_schedules(equipment_id);
CREATE INDEX idx_equip_schedules_time ON equipment_schedules(start_time, end_time);
```

Double-booking prevention is handled at the application layer.

**1.2.7 — Authorization Sessions & Enrollments**

```sql
CREATE TABLE IF NOT EXISTS equip_auth_sessions (
    id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    equipment_ids   INTEGER[] DEFAULT '{}',
    authorizer_id   INTEGER NOT NULL REFERENCES member(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT,
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ NOT NULL,
    total_slots     INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_equip_auth_sessions_time ON equip_auth_sessions(start_time);

CREATE TABLE IF NOT EXISTS equip_auth_enrollments (
    id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    session_id      INTEGER NOT NULL REFERENCES equip_auth_sessions(id) ON DELETE CASCADE,
    member_id       INTEGER NOT NULL REFERENCES member(id) ON DELETE CASCADE,
    enrolled_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(session_id, member_id)
);
```

**1.2.8 — Equipment Module Configuration**

```sql
CREATE TABLE IF NOT EXISTS equipment_config (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL DEFAULT '{}',
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_by  INTEGER REFERENCES member(id)
);
```

### 1.3 — Auto-Update Triggers

```sql
CREATE OR REPLACE FUNCTION equip_update_version()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    NEW.version = OLD.version + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_equipment_ver BEFORE UPDATE ON equipment
    FOR EACH ROW EXECUTE FUNCTION equip_update_version();
CREATE TRIGGER trg_tickets_ver BEFORE UPDATE ON repair_tickets
    FOR EACH ROW EXECUTE FUNCTION equip_update_version();
```

### 1.4 — OAuth2 Client for DHEquipmentPortal

```sql
INSERT INTO oauth2_users (client_name, client_secret, client_description)
VALUES (
    'dev-equipment-portal',
    -- Generate with: tools/generate_secret.sh
    '$2b$12$PLACEHOLDER_REPLACE_BEFORE_DEPLOY',
    'Equipment management portal application'
);
```

### 1.5 — Update Existing Roles for Equipment Access

Migration SQL to add equipment permissions to Administrator (id=2) and SuperAdmin (id=5):

```sql
UPDATE roles SET permission = jsonb_set(
    jsonb_set(permission, '{view}',
        permission->'view' || '["equipment.areas","equipment.items","equipment.groups","equipment.tickets","equipment.schedules","equipment.auth_sessions","equipment.maintenance","equipment.dashboard","equipment.config"]'::jsonb
    ), '{change}',
    permission->'change' || '["equipment.areas","equipment.items","equipment.groups","equipment.tickets","equipment.schedules","equipment.auth_sessions","equipment.maintenance","equipment.config"]'::jsonb
) WHERE id = 2;

UPDATE roles SET permission = jsonb_set(
    jsonb_set(permission, '{view}',
        permission->'view' || '["equipment.areas","equipment.items","equipment.groups","equipment.tickets","equipment.schedules","equipment.auth_sessions","equipment.maintenance","equipment.dashboard","equipment.config"]'::jsonb
    ), '{change}',
    permission->'change' || '["equipment.areas","equipment.items","equipment.groups","equipment.tickets","equipment.schedules","equipment.auth_sessions","equipment.maintenance","equipment.config"]'::jsonb
) WHERE id = 5;
```

---

## Phase 2: Row Level Security

### 2.1 — Application Role

```sql
CREATE ROLE dh_app LOGIN PASSWORD 'CHANGE_ME_VIA_ENV';

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    member, member_audit, oauth2_users,
    roles, member_to_role, user_activity_logs,
    rfid_board_sync, waivers, subscriptions, products,
    email_templates, email_template_parameters,
    service_endpoints, membership_types_lookup,
    available_authorizations, member_changes,
    member_changes_processing_log, member_access_log,
    areas, equipment, equipment_groups,
    equipment_group_members, repair_tickets,
    maintenance_schedules, maintenance_events,
    equipment_schedules, equip_auth_sessions,
    equip_auth_enrollments, equipment_config
TO dh_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO dh_app;
```

### 2.2 — Audit Infrastructure

Separate `equipment_audit_log` table (may merge with a global audit log later once RLS is implemented everywhere):

```sql
CREATE TABLE IF NOT EXISTS equipment_audit_log (
    id              BIGSERIAL PRIMARY KEY,
    table_name      TEXT NOT NULL,
    record_id       TEXT,
    operation       TEXT NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE')),
    user_id         TEXT,
    user_role       TEXT,
    old_data        JSONB,
    new_data        JSONB,
    changed_fields  TEXT[],
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_equip_audit_table ON equipment_audit_log(table_name);
CREATE INDEX idx_equip_audit_record ON equipment_audit_log(record_id);
CREATE INDEX idx_equip_audit_time ON equipment_audit_log(created_at);
```

Port PA1's `audit_trigger_fn()` as `SECURITY DEFINER` and attach to all equipment tables. The `dh_app` role gets `SELECT` only on the audit log. Session context uses PA1's hardened `set_config()` pattern (parameterized, not string-interpolated).

### 2.3 — RLS Policies

Permissive to start — open reads, open writes for `dh_app` — with the exception of `equipment_config` which is gated by session role:

```sql
ALTER TABLE equipment_config ENABLE ROW LEVEL SECURITY;
CREATE POLICY config_select ON equipment_config FOR SELECT USING (true);
CREATE POLICY config_modify ON equipment_config FOR UPDATE USING (
    current_setting('app.session_role', true) IN ('Administrator', 'SuperAdmin', 'Area Host')
    OR COALESCE(current_setting('app.session_role', true), '') = ''
);
```

### 2.4 — Migration Strategy

1. Create `dh_app` role and grants (non-destructive, coexists with `dh` superuser)
2. DHEquipment service uses `dh_app` from day one
3. Validate RLS on equipment tables
4. Migrate existing DH services from `dh` to `dh_app` one at a time in Sprint 6

---

## Phase 3: DHEquipment Service (Backend)

### 3.1 — Service Location & Tooling

```
code/services/DHEquipment/
├── Dockerfile          # Python 3.14-slim + uv
├── main.py             # FastAPI app + health check + /token endpoint
├── v1.py               # All /v1/equipment/* endpoints
├── auth.py             # Copy of DHService/auth.py (OAuth2 client credentials)
├── config.py           # configparser loader
├── config.ini.example
├── db.py               # psycopg2 database operations
├── models.py           # Pydantic models + Client dataclass
├── dhs_logging.py      # Standard DH logging
├── pyproject.toml      # uv-managed, Python ≥3.14
└── start_services.sh
```

Dockerfile follows DHService pattern:
```dockerfile
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN apt-get update && apt-get install -y curl
COPY . /app
WORKDIR /app
RUN uv sync --frozen --no-cache
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3.2 — Key Porting Differences

| Aspect | PA1 (Source) | DHEquipment (Target) |
|---|---|---|
| DB driver | asyncpg (`$1`, `await conn.fetch()`) | psycopg2 (`%s`, cursor-based) |
| JWT library | python-jose (`from jose import jwt`) | PyJWT (`import jwt`) |
| Primary keys | UUID | INTEGER |
| Auth | OAuth2 password flow (user login) | OAuth2 client credentials |
| Session context | `set_config()` parameterized | Same pattern (port directly) |

### 3.3 — Authentication Flow

Copy `auth.py`, `config.py`, `models.py`, `dhs_logging.py`, and `fastapiapp.py` from DHService. Portal authenticates with `dev-equipment-portal` client credentials. User identity and permissions passed via request headers (`X-Member-ID`, `X-Member-Permissions`) set by the portal's Flask backend after SSO.

### 3.4 — What Gets Ported from PA1

**Ported:**
- Equipment CRUD, Areas CRUD, Repair Tickets, Scheduling, Auth Sessions, Equipment Groups, Maintenance — all adapted for integer PKs and psycopg2
- File uploads (via RustFS)
- Permission checking (adapted to DH's `roles` + `member_to_role` tables, `equipment.*` namespace)
- Dashboard stats
- Config CRUD
- Notification/webhook system

**Not ported:**
- User management (`/api/users/*`, login/registration)
- Branding/theme system
- Authentication provider config (OIDC, LDAP, SAML)

### 3.5 — Permission Checking

DHEquipment accepts `X-Member-ID` and `X-Member-Permissions` headers from the portal. A `check_equipment_perm(required: str)` FastAPI dependency validates permissions against the `equipment.*` namespace.

### 3.6 — API Endpoints

All under `/v1/equipment/` prefix:

```
Areas:          GET|POST /areas, PATCH|DELETE /areas/{id}
Equipment:      GET|POST /items, GET|PATCH|DELETE /items/{id}
Groups:         GET|POST /groups, PATCH|DELETE /groups/{id}
Tickets:        GET|POST /tickets, PATCH|DELETE /tickets/{id}
                POST /tickets/{id}/worklog
Schedules:      GET|POST /schedules, DELETE /schedules/{id}
Auth Sessions:  GET|POST /auth-sessions
                POST|DELETE /auth-sessions/{id}/enroll
Maintenance:    GET|POST /maintenance/schedules
                GET|PATCH /maintenance/events, /events/{id}
Dashboard:      GET /dashboard/stats
Config:         GET|PUT /config/{key}
Upload:         POST /upload
Export:         GET /export/{entity}
```

---

## Phase 4: DHEquipmentPortal (Frontend)

### 4.1 — Service Location

```
code/DHEquipmentPortal/
├── Dockerfile              # Python 3.14-slim + uv
├── app.py                  # Flask app (DHAdminPortal pattern)
├── app_config.py           # Azure B2C config
├── config.py
├── config.ini.example
├── dhservices.py            # HTTP client: DHService + DHEquipment APIs
├── dhs_logging.py
├── pyproject.toml
├── static/
│   ├── styles.css           # DH theme system with Clean theme
│   └── images/
└── templates/
    ├── base.html            # DH theme switcher, CSRF, nav
    ├── index.html           # Adapted PA1 SPA
    └── dev_login.html
```

### 4.2 — SSO and Auth

Copy DHAdminPortal's MSAL-based Azure B2C flow wholesale: dev-mode bypass, CSRF tokens, Flask session with role/permission storage, permission-gated decorators. Adapt permission namespace to `equipment.*`.

### 4.3 — Adapting PA1's Frontend

1. **Strip PA1's auth** — remove login form, JWT localStorage, token refresh. Replace with Jinja2-injected session data.
2. **Replace API calls** — direct `/api/*` calls become Flask-proxied routes through `dhservices.py`.
3. **Replace permission model** — `can()` reads from Jinja2-injected `USER_PERMISSIONS` instead of JWT.
4. **Adopt DH's theme system** — replace `--pa1-*` CSS variables with `data-theme` attribute system. Add new "Clean" theme as the default for equipment portal.
5. **Strip panels handled by DH** — remove Users, Authentication, Branding, About/API Docs. Keep Equipment, Areas, Tickets, Scheduling, Authorizations, Groups, Maintenance, Dashboard, Modules, Templates, Notifications, Export/Import.

### 4.4 — Clean Theme

A new 6th theme added to DH's `data-theme` system. Default for the equipment portal.

```css
[data-theme="clean"] {
    --primary-color: #6f42c1;
    --bg-color: #f8fafc;
    --surface-color: #ffffff;
    --header-color: #ffffff;
    --sidebar-color: #ffffff;
    --text-color: #212529;
}
```

Characteristics:
- White background, white header, white sidebar
- Purple (`#6f42c1`) primary buttons, active nav highlights, links
- White text on purple buttons
- System UI font stack, no decorative fonts
- No animations, sparkles, or background effects

Available in the theme switcher on all portals alongside the existing 5 themes.

### 4.5 — Permission Section Map

```javascript
const SECTIONS = ['dashboard', 'equipment', 'tickets', 'areas',
                  'scheduling', 'authorizations', 'groups',
                  'maintenance', 'settings'];

const SECTION_PERM_MAP = {
    dashboard:      'equipment.dashboard',
    equipment:      'equipment.items',
    tickets:        'equipment.tickets',
    areas:          'equipment.areas',
    scheduling:     'equipment.schedules',
    authorizations: 'equipment.auth_sessions',
    groups:         'equipment.groups',
    maintenance:    'equipment.maintenance',
    settings:       'equipment.config',
};
```

---

## Phase 5: Docker & Infrastructure

### 5.1 — docker-compose.yaml Additions

```yaml
  # Equipment Management Service
  dhequipment:
    build: ./code/services/DHEquipment
    restart: unless-stopped
    environment:
      TZ: "America/Chicago"
      SERVICE_NAME: DH_EQUIPMENT
      DATABASE_HOST: db
      DATABASE_PORT: 5432
      DATABASE_NAME: deepharbor
      DATABASE_USER: dh_app
      DATABASE_PASSWORD: ${DH_APP_PASSWORD}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    expose:
      - "8000"
    depends_on:
      db:
        condition: service_healthy
    container_name: dh_equipment
    networks:
      - dh_network

  # Equipment Portal (Frontend)
  dhequipmentportal:
    build:
      context: ./code/DHEquipmentPortal
      args:
        GIT_VERSION: "${GIT_VERSION}"
    restart: unless-stopped
    network_mode: host
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5003/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    ports:
      - "5003:5003"
    depends_on:
      dhequipment:
        condition: service_healthy
      dhservice:
        condition: service_healthy
    container_name: dh_equipment_portal
    environment:
      TZ: "America/Chicago"
      DH_SECRET_KEY: "${DH_SECRET_KEY}"

  # RustFS (S3-compatible object storage)
  rustfs:
    image: rustfs/rustfs:latest
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      RUSTFS_ACCESS_KEY: ${RUSTFS_ACCESS_KEY:-deepharbor}
      RUSTFS_SECRET_KEY: ${RUSTFS_SECRET_KEY}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - rustfs_data:/data
    container_name: dh_rustfs
    networks:
      - dh_network
```

Add `rustfs_data:` to the `volumes:` section.

### 5.2 — nginx.conf Additions

```nginx
upstream dhequipment {
    server dhequipment:8000;
}

# Inside the server block:
location /dh/equipment/ {
    proxy_pass http://dhequipment/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 110m;
}

location /files/ {
    proxy_pass http://rustfs:9000/;
    proxy_set_header Host rustfs:9000;
    client_max_body_size 110m;
}
```

Add `dhequipment` to the gateway's `depends_on`.

---

## Implementation Sprints

### Sprint 1: Database Foundation

- [ ] Fork `pumpingstationone/deepharbor`, branch off `dev`
- [ ] Add all new tables to `pgsql_schema.sql` (1.2.1 through 1.2.8)
- [ ] Add auto-update triggers (1.3)
- [ ] Add Area Host and Technician roles (1.1)
- [ ] Add OAuth2 client for equipment portal (1.4)
- [ ] Create `pg/sql/migrate_equipment.sql` for updating existing roles (1.5)
- [ ] Create `dh_app` role and grants (2.1)
- [ ] Add equipment audit log table and trigger (2.2)
- [ ] Add initial RLS policies (2.3)
- [ ] Test: `docker-compose down -v && docker-compose up --build` — verify clean startup
- [ ] Test: connect as `dh_app`, verify grants and RLS policies

### Sprint 2: DHEquipment Service

- [ ] Scaffold `code/services/DHEquipment/` with Dockerfile, pyproject.toml (uv, Python ≥3.14)
- [ ] Copy auth.py, config.py, models.py, dhs_logging.py, fastapiapp.py from DHService
- [ ] Create config.ini.example
- [ ] Port PA1 database queries into db.py — convert asyncpg → psycopg2, UUID → integer
- [ ] Port PA1 CRUD endpoints into v1.py
- [ ] Implement `equipment.*` permission checking via `X-Member-*` headers
- [ ] Implement session context setting for RLS (`set_config()` pattern)
- [ ] Add docker-compose service block
- [ ] Add nginx upstream and location block
- [ ] Run `uv sync` and verify Dockerfile builds
- [ ] Test all endpoints via curl

### Sprint 3: DHEquipmentPortal

- [ ] Scaffold `code/DHEquipmentPortal/` (Dockerfile, pyproject.toml with uv)
- [ ] Copy auth flow from DHAdminPortal (app.py, app_config.py, config.py, dev_login.html)
- [ ] Implement `dhservices.py` client for DHService + DHEquipment APIs
- [ ] Adapt PA1's `index.html`:
  - [ ] Strip PA1 auth (login form, JWT, token refresh)
  - [ ] Replace API calls with Flask-proxied routes
  - [ ] Replace permission source (JWT → Jinja2 template variable)
  - [ ] Strip non-equipment panels (Users, Auth Config, Branding, About)
- [ ] Create `base.html` from DHAdminPortal dev template
- [ ] Implement Clean theme (`data-theme="clean"`, purple `#6f42c1` primary, white surfaces, no effects)
- [ ] Add Clean theme to all portals' theme switcher
- [ ] Set Clean as default theme for equipment portal
- [ ] Add docker-compose service block
- [ ] Generate OAuth2 secret with `tools/generate_secret.sh`
- [ ] Test: dev-mode login → dashboard → navigate all sections
- [ ] Test: Azure B2C login flow (if B2C env available)

### Sprint 4: File Storage & Polish

- [ ] Add RustFS service to docker-compose
- [ ] Add nginx `/files/` proxy location
- [ ] Port PA1's file upload endpoint and S3 client to DHEquipment (boto3 → RustFS)
- [ ] Port PA1's notification/webhook system
- [ ] Add Equipment nav link to DHAdminPortal navbar
- [ ] Cross-portal permission consistency check
- [ ] Test with representative data volume

### Sprint 5: Discord Bot

- [ ] Scaffold `code/services/DHDiscordBot/` (or `code/external/DHDiscordBot/`)
- [ ] Port PA1's `discord-bot/bot.py` and `config.yaml`
- [ ] Adapt `pa1_api.py` client:
  - [ ] Change auth from PA1 password flow to DH OAuth2 client credentials
  - [ ] Update API paths from `/api/*` to gateway paths `/dh/equipment/v1/equipment/*`
  - [ ] Update ID handling from UUID to integer
- [ ] Add OAuth2 client entry for the bot in `oauth2_users`
- [ ] Add docker-compose service block
- [ ] Update config.yaml defaults for DH branding
- [ ] Test: slash commands create tickets, add work log entries, search equipment

### Sprint 6: RLS Rollout & Integration

- [ ] Confirm DHEquipment is stable on `dh_app` role
- [ ] Add `SET LOCAL app.session_role` to DHService per-request
- [ ] Migrate DHService to `dh_app` credentials
- [ ] Migrate remaining services one at a time (DHDispatcher, business services, workers)
- [ ] Validate all existing functionality works under `dh_app`
- [ ] Security review of RLS policies
- [ ] Update documentation (README, DEV_SETUP.md)
- [ ] PR to `pumpingstationone/deepharbor` `dev`

---

## Compatibility Reference

| Aspect | Deep Harbor (dev) | Purple Asset One |
|---|---|---|
| Python version | ≥ 3.14 | 3.12 |
| Package manager | uv + pyproject.toml | pip + requirements.txt |
| DB driver | psycopg2 (sync) | asyncpg (async) |
| SQL placeholders | `%s` | `$1, $2` |
| JWT library | PyJWT (`import jwt`) | python-jose (`from jose import jwt`) |
| User primary key | `INTEGER` (`member.id`) | `UUID` (`users.id`) |
| User auth | Azure B2C SSO (MSAL) | Local username/password (JWT) |
| API auth | OAuth2 client credentials | OAuth2 password flow |
| Permission format | `"namespace.key"` in JSONB `{view:[], change:[]}` | Flat string list from computed grants |
| Role storage | `roles` table → `member_to_role` mapping | `users.role` column (CHECK constraint) |
| Theme system | `data-theme` attr + CSS vars + cookie | `applyTheme()` JS + DB-stored config |
| Frontend framework | Flask + Jinja2 templates | Single-file SPA (vanilla JS) |
| CSS framework | Bootstrap 5.3.3 | Bootstrap 5.3 (CDN) |
| Icons | Font Awesome 6.7 | Bootstrap Icons |
| File storage | RustFS (new) | MinIO |
| Session context | `set_config()` parameterized | `set_config()` parameterized |

---

## File Change Summary

| File | Action |
|---|---|
| `pg/sql/pgsql_schema.sql` | **Modify** — append ~250 lines (tables, triggers, roles) |
| `pg/sql/migrate_equipment.sql` | **New** — migration for existing deployments |
| `docker-compose.yaml` | **Modify** — add DHEquipment, DHEquipmentPortal, RustFS |
| `nginx.conf` | **Modify** — add upstream + location blocks |
| `code/services/DHEquipment/` | **New** — entire backend service (~10 files) |
| `code/DHEquipmentPortal/` | **New** — entire frontend portal (~10 files + adapted PA1 frontend) |
| `code/DHAdminPortal/templates/base.html` | **Modify** — add Equipment link to navbar |
| `code/DHAdminPortal/static/styles.css` | **Modify** — add Clean theme CSS block |
| `code/services/DHDiscordBot/` | **New** — adapted Discord bot (~5 files) |
