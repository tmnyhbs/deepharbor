# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "faker>=33.0.0",
# ]
# ///
"""
Generate seed data SQL for the Deep Harbor CRM database.

Produces INSERT statements for the member table with realistic
fictional data. Always includes 10 hardcoded "dev bypass" users
(IDs 1-10) first, then generates additional random members.

Usage:
    uv run pg/tools/generate_seed_data.py
    uv run pg/tools/generate_seed_data.py --seed abc123 --count 50
    uv run pg/tools/generate_seed_data.py --count 100 --output pg/sql/seed_data.sql
"""

import argparse
import hashlib
import json
import random
import secrets
import sys
from datetime import timedelta

from faker import Faker


### Lookup data — copied from pgsql_schema.sql

MEMBERSHIP_TYPES = [
    "Area Host",
    "Board Member / Officer",
    "Contractor",
    "Member - Cash Payment",
    "Member - Grandfathered Price",
    "Member - PayPal",
    "Member w/ Storage - Cash Payment",
    "Member w/ Storage - Grandfathered Price",
    "Member w/ Storage - PayPal",
    "New Member",
    "Scholarship",
    "Stripe Member - $65",
    "Stripe Member w/ Storage - $95",
    "Stripe Volunteer w/ Paid Storage - $30",
    "Volunteer",
    "Volunteer w/ Free Storage",
    "Volunteer w/ Paid Storage",
]

# Weighted distribution for random member generation — favors
# the more common membership types over special ones
MEMBERSHIP_WEIGHTS = {
    "Stripe Member - $65": 25,
    "Member - Cash Payment": 15,
    "Member - PayPal": 10,
    "Stripe Member w/ Storage - $95": 8,
    "Member w/ Storage - Cash Payment": 5,
    "Member w/ Storage - PayPal": 5,
    "Member w/ Storage - Grandfathered Price": 3,
    "Member - Grandfathered Price": 5,
    "Volunteer": 6,
    "Volunteer w/ Free Storage": 3,
    "Volunteer w/ Paid Storage": 3,
    "Stripe Volunteer w/ Paid Storage - $30": 3,
    "Scholarship": 3,
    "New Member": 2,
    "Area Host": 1,
    "Contractor": 2,
    "Board Member / Officer": 1,
}

# requires_login=true — these go in "computer_authorizations"
COMPUTER_AUTHORIZATIONS = [
    "Boss Authorized Users",
    "CNC Plasma Authorized Users",
    "Epilog Authorized Users",
    "ShopBot Authorized Users",
    "Tormach Authorized Users",
    "Universal Authorized Users",
    "Vinyl Cutter Authorized Users",
    "Mimaki CJV30 printer Users",
]

# requires_login=false — these go in "authorizations"
PHYSICAL_AUTHORIZATIONS = [
    "Band Saw",
    "Billiards",
    "Blacksmithing",
    "Bridgeport Mill",
    "Button sewing machines",
    "Clausing Lathe",
    "Coffee Roaster",
    "Cold Metals Basic",
    "Drum Sander",
    "Ender 3D Printers",
    "Formlabs Form 3 printer",
    "Hand held plasma cutter",
    "Jointer",
    "LeBlond Lathe",
    "Metal Band Saw",
    "Metal Drill Press",
    "Mig Welders",
    "Mitre Saw",
    "Multi-Router",
    "Panel Saw",
    "Planer",
    "Pneumatic Power Tools",
    "Powder Coating Equipment",
    "Prusa 3D printers",
    "Router Table",
    "Sanders",
    "Saw Dado",
    "Serger sewing machine",
    "Square Chisel Morticer",
    "Surface Grinder",
    "Table Saw",
    "Tier one Sewing Machine",
    "Tig Welders",
    "Tube Bending Equipment",
    "Wood Drill Press",
    "Wood Lathe",
    "Wood Mini Lathe",
]

STORAGE_AREAS = [
    "North Wall",
    "South Wall",
    "East Wall",
    "West Wall",
    "Woodshop Corner",
    "Metalshop",
    "Electronics Bench",
    "Classroom",
    "Main Floor",
    "Mezzanine",
]


### Dev bypass users — these are always the same, always first

DEV_USERS = [
    # ID 1 - Ada Lovelace, Administrator
    {
        "identity": {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "nickname": "enchantress_of_numbers",
            "active_directory_username": "alovelace",
            "emails": [{"type": "primary", "email_address": "ada.lovelace@example.com"}],
        },
        "connections": {"discord_username": "ada_admin"},
        "status": {
            "membership_status": "Active",
            "membership_level": "Stripe Member - $65",
            "member_since": "2020-01-15",
        },
        "forms": {
            "id_check_1": "IL",
            "id_check_2": "DL-1234",
            "waiver_signed_date": "2020-01-15",
            "terms_of_use_accepted": "true",
            "essentials_form": "completed",
            "orientation_completed_date": "2020-01-22",
        },
        "access": {"rfid_tags": ["1012345678", "1087654321"]},
        "authorizations": {
            "authorizations": [
                "Table Saw", "Band Saw", "Mig Welders", "Tig Welders",
                "Jointer", "Planer", "Mitre Saw", "Sanders",
                "Wood Drill Press", "Router Table",
            ],
            "computer_authorizations": [
                "Epilog Authorized Users", "Tormach Authorized Users",
                "ShopBot Authorized Users",
            ],
        },
        "extras": {"storage_id": "A-01", "storage_area": "North Wall"},
        "notes": {
            "notes": [
                {"date": "2020-01-22", "author": "System", "text": "Completed orientation and safety training"},
                {"date": "2023-06-10", "author": "Board", "text": "Granted administrator access to the admin portal"},
            ]
        },
    },
    # ID 2 - Charles Babbage, Administrator
    {
        "identity": {
            "first_name": "Charles",
            "last_name": "Babbage",
            "nickname": "difference_engine",
            "active_directory_username": "cbabbage",
            "emails": [{"type": "primary", "email_address": "charles.babbage@example.com"}],
        },
        "connections": {"discord_username": "cbabbage"},
        "status": {
            "membership_status": "Active",
            "membership_level": "Member - Cash Payment",
            "member_since": "2019-03-10",
        },
        "forms": {
            "id_check_1": "IL",
            "id_check_2": "DL-5678",
            "waiver_signed_date": "2019-03-10",
            "terms_of_use_accepted": "true",
            "essentials_form": "completed",
            "orientation_completed_date": "2019-03-17",
        },
        "access": {"rfid_tags": ["1023456789"]},
        "authorizations": {
            "authorizations": [
                "Table Saw", "Band Saw", "Metal Band Saw",
                "Metal Drill Press", "Bridgeport Mill", "Clausing Lathe",
            ],
            "computer_authorizations": [
                "Boss Authorized Users", "CNC Plasma Authorized Users",
            ],
        },
        "extras": None,
        "notes": {
            "notes": [
                {"date": "2019-03-17", "author": "System", "text": "Orientation completed"},
                {"date": "2024-01-15", "author": "Board", "text": "Added as administrator"},
            ]
        },
    },
    # ID 3 - Nikola Tesla, Authorizer
    {
        "identity": {
            "first_name": "Nikola",
            "last_name": "Tesla",
            "nickname": "spark_lord",
            "active_directory_username": "ntesla",
            "emails": [{"type": "primary", "email_address": "nikola.tesla@example.com"}],
        },
        "connections": {"discord_username": "spark_lord"},
        "status": {
            "membership_status": "Active",
            "membership_level": "Volunteer",
            "member_since": "2018-06-01",
        },
        "forms": {
            "id_check_1": "IL",
            "id_check_2": "PP-9012",
            "waiver_signed_date": "2018-06-01",
            "terms_of_use_accepted": "true",
            "essentials_form": "completed",
            "orientation_completed_date": "2018-06-08",
        },
        "access": {"rfid_tags": ["1011223344"]},
        "authorizations": {
            "authorizations": [
                "Table Saw", "Band Saw", "Mig Welders", "Tig Welders",
                "Jointer", "Planer", "Mitre Saw", "Sanders",
                "Wood Drill Press", "Router Table", "Metal Band Saw",
                "Metal Drill Press", "Bridgeport Mill", "Clausing Lathe",
                "LeBlond Lathe", "Surface Grinder", "Hand held plasma cutter",
                "Pneumatic Power Tools", "Powder Coating Equipment",
                "Tube Bending Equipment",
            ],
            "computer_authorizations": [
                "Epilog Authorized Users", "Tormach Authorized Users",
                "Universal Authorized Users", "Boss Authorized Users",
                "CNC Plasma Authorized Users", "ShopBot Authorized Users",
            ],
        },
        "extras": None,
        "notes": {
            "notes": [
                {"date": "2018-06-08", "author": "System", "text": "Completed orientation"},
                {"date": "2019-02-14", "author": "Board", "text": "Approved as equipment authorizer for metalworking and CNC areas"},
            ]
        },
    },
    # ID 4 - Hedy Lamarr, Authorizer
    {
        "identity": {
            "first_name": "Hedy",
            "last_name": "Lamarr",
            "nickname": "frequency_hopper",
            "active_directory_username": "hlamarr",
            "emails": [{"type": "primary", "email_address": "hedy.lamarr@example.com"}],
        },
        "connections": {"discord_username": "hedy_builds"},
        "status": {
            "membership_status": "Active",
            "membership_level": "Volunteer w/ Free Storage",
            "member_since": "2019-09-15",
        },
        "forms": {
            "id_check_1": "IL",
            "id_check_2": "DL-3456",
            "waiver_signed_date": "2019-09-15",
            "terms_of_use_accepted": "true",
            "essentials_form": "completed",
            "orientation_completed_date": "2019-09-22",
        },
        "access": {"rfid_tags": ["1044556677", "1055667788"]},
        "authorizations": {
            "authorizations": [
                "Table Saw", "Band Saw", "Wood Lathe", "Wood Mini Lathe",
                "Drum Sander", "Panel Saw", "Saw Dado",
                "Square Chisel Morticer", "Jointer", "Planer",
                "Ender 3D Printers", "Prusa 3D printers",
                "Formlabs Form 3 printer",
            ],
            "computer_authorizations": [
                "Epilog Authorized Users", "Universal Authorized Users",
                "Vinyl Cutter Authorized Users", "Mimaki CJV30 printer Users",
            ],
        },
        "extras": {"storage_id": "C-05", "storage_area": "Woodshop Corner"},
        "notes": {
            "notes": [
                {"date": "2019-09-22", "author": "System", "text": "Completed orientation and all woodshop authorizations"},
                {"date": "2020-04-01", "author": "Board", "text": "Approved as authorizer for woodshop, 3D printing, and laser areas"},
            ]
        },
    },
    # ID 5 - Grace Hopper, Board
    {
        "identity": {
            "first_name": "Grace",
            "last_name": "Hopper",
            "nickname": "queen_bug",
            "active_directory_username": "ghopper",
            "emails": [{"type": "primary", "email_address": "grace.hopper@example.com"}],
        },
        "connections": {"discord_username": "admiral_grace"},
        "status": {
            "membership_status": "Active",
            "membership_level": "Board Member / Officer",
            "member_since": "2017-11-01",
        },
        "forms": {
            "id_check_1": "IL",
            "id_check_2": "DL-7890",
            "waiver_signed_date": "2017-11-01",
            "terms_of_use_accepted": "true",
            "essentials_form": "completed",
            "orientation_completed_date": "2017-11-08",
        },
        "access": {"rfid_tags": ["1099887766"]},
        "authorizations": {
            "authorizations": ["Ender 3D Printers", "Prusa 3D printers", "Band Saw"],
            "computer_authorizations": [],
        },
        "extras": None,
        "notes": {
            "notes": [
                {"date": "2017-11-08", "author": "System", "text": "Completed orientation"},
                {"date": "2022-01-01", "author": "Board", "text": "Elected to board of directors"},
            ]
        },
    },
    # ID 6 - Margaret Hamilton, Board
    {
        "identity": {
            "first_name": "Margaret",
            "last_name": "Hamilton",
            "nickname": "stack_overflow",
            "active_directory_username": "mhamilton",
            "emails": [{"type": "primary", "email_address": "margaret.hamilton@example.com"}],
        },
        "connections": {"discord_username": "mhamilton_apollo"},
        "status": {
            "membership_status": "Active",
            "membership_level": "Board Member / Officer",
            "member_since": "2018-03-15",
        },
        "forms": {
            "id_check_1": "IL",
            "id_check_2": "DL-2345",
            "waiver_signed_date": "2018-03-15",
            "terms_of_use_accepted": "true",
            "essentials_form": "completed",
            "orientation_completed_date": "2018-03-22",
        },
        "access": {"rfid_tags": ["1077665544"]},
        "authorizations": {
            "authorizations": ["Table Saw", "Mitre Saw", "Sanders", "Ender 3D Printers"],
            "computer_authorizations": ["Epilog Authorized Users"],
        },
        "extras": None,
        "notes": {
            "notes": [
                {"date": "2018-03-22", "author": "System", "text": "Completed orientation"},
                {"date": "2023-01-01", "author": "Board", "text": "Elected to board"},
            ]
        },
    },
    # ID 7 - Rosalind Franklin, Active Member
    {
        "identity": {
            "first_name": "Rosalind",
            "last_name": "Franklin",
            "nickname": "photo_51",
            "active_directory_username": "rfranklin",
            "emails": [{"type": "primary", "email_address": "rosalind.franklin@example.com"}],
        },
        "connections": {"discord_username": "xray_rosalind"},
        "status": {
            "membership_status": "Active",
            "membership_level": "Member - Cash Payment",
            "member_since": "2021-04-01",
        },
        "forms": {
            "id_check_1": "IL",
            "id_check_2": "DL-6789",
            "waiver_signed_date": "2021-04-01",
            "terms_of_use_accepted": "true",
            "essentials_form": "completed",
            "orientation_completed_date": "2021-04-08",
        },
        "access": {"rfid_tags": ["1033221100", "1044332211"]},
        "authorizations": {
            "authorizations": [
                "Table Saw", "Band Saw", "Mig Welders", "Jointer",
                "Planer", "Ender 3D Printers", "Prusa 3D printers",
            ],
            "computer_authorizations": [
                "Epilog Authorized Users", "Tormach Authorized Users",
            ],
        },
        "extras": {"storage_id": "B-12", "storage_area": "South Wall"},
        "notes": {
            "notes": [
                {"date": "2021-04-08", "author": "System", "text": "Completed orientation and basic woodshop training"},
            ]
        },
    },
    # ID 8 - Katherine Johnson, Active Member
    {
        "identity": {
            "first_name": "Katherine",
            "last_name": "Johnson",
            "nickname": "human_computer",
            "active_directory_username": "kjohnson",
            "emails": [{"type": "primary", "email_address": "katherine.johnson@example.com"}],
        },
        "connections": {"discord_username": "kjohnson_math"},
        "status": {
            "membership_status": "Active",
            "membership_level": "Stripe Member - $65",
            "member_since": "2022-02-14",
        },
        "forms": {
            "id_check_1": "IL",
            "id_check_2": "DL-0123",
            "waiver_signed_date": "2022-02-14",
            "terms_of_use_accepted": "true",
            "essentials_form": "completed",
            "orientation_completed_date": "2022-02-21",
        },
        "access": {"rfid_tags": ["1066778899"]},
        "authorizations": {
            "authorizations": [
                "Ender 3D Printers", "Prusa 3D printers",
                "Formlabs Form 3 printer", "Tier one Sewing Machine",
                "Serger sewing machine", "Button sewing machines",
            ],
            "computer_authorizations": [
                "Epilog Authorized Users", "Vinyl Cutter Authorized Users",
            ],
        },
        "extras": None,
        "notes": {
            "notes": [
                {"date": "2022-02-21", "author": "System", "text": "Completed orientation, focused on textiles and 3D printing"},
            ]
        },
    },
    # ID 9 - Marie Curie, Inactive Member
    {
        "identity": {
            "first_name": "Marie",
            "last_name": "Curie",
            "nickname": "glow_girl",
            "active_directory_username": "mcurie",
            "emails": [{"type": "primary", "email_address": "marie.curie@example.com"}],
        },
        "connections": {"discord_username": "mcurie_rad"},
        "status": {
            "membership_status": "Inactive",
            "membership_level": "Member - Cash Payment",
            "member_since": "2018-06-01",
        },
        "forms": {
            "id_check_1": "IL",
            "id_check_2": "DL-4567",
            "waiver_signed_date": "2018-06-01",
            "terms_of_use_accepted": "true",
            "essentials_form": "completed",
            "orientation_completed_date": "2018-06-08",
        },
        "access": {"rfid_tags": ["1033445566"]},
        "authorizations": {
            "authorizations": ["Table Saw", "Band Saw", "Mig Welders", "Cold Metals Basic"],
            "computer_authorizations": [],
        },
        "extras": None,
        "notes": {
            "notes": [
                {"date": "2018-06-08", "author": "System", "text": "Completed orientation"},
                {"date": "2024-03-01", "author": "System", "text": "Membership lapsed \u2014 moved to inactive"},
            ]
        },
    },
    # ID 10 - Laika Sputnik, Inactive Member
    {
        "identity": {
            "first_name": "Laika",
            "last_name": "Sputnik",
            "nickname": "good_dog",
            "active_directory_username": "lsputnik",
            "emails": [{"type": "primary", "email_address": "laika.sputnik@example.com"}],
        },
        "connections": None,
        "status": {
            "membership_status": "Inactive",
            "membership_level": "Stripe Member - $65",
            "member_since": "2023-09-01",
        },
        "forms": {
            "id_check_1": "IL",
            "id_check_2": "DL-8901",
            "waiver_signed_date": "2023-09-01",
            "terms_of_use_accepted": "true",
            "essentials_form": "completed",
            "orientation_completed_date": "2023-09-08",
        },
        "access": None,
        "authorizations": {
            "authorizations": ["Band Saw", "Ender 3D Printers"],
            "computer_authorizations": [],
        },
        "extras": None,
        "notes": {
            "notes": [
                {"date": "2023-09-08", "author": "System", "text": "Completed orientation"},
                {"date": "2024-06-01", "author": "System", "text": "Membership lapsed after 9 months"},
            ]
        },
    },
]

# RFID tags used by dev users — we track these so the generator
# doesn't accidentally duplicate them in random members
DEV_USER_RFID_TAGS = set()
DEV_USER_USERNAMES = set()
DEV_USER_EMAILS = set()
for _user in DEV_USERS:
    if _user.get("access") and _user["access"].get("rfid_tags"):
        DEV_USER_RFID_TAGS.update(_user["access"]["rfid_tags"])
    if _user["identity"].get("active_directory_username"):
        DEV_USER_USERNAMES.add(_user["identity"]["active_directory_username"])
    for email_entry in _user["identity"].get("emails", []):
        DEV_USER_EMAILS.add(email_entry["email_address"])


### SQL generation helpers

def make_member_sql(member: dict) -> str:
    """Convert a member dict to an INSERT INTO member (...) VALUES (...) statement."""
    columns = [
        "identity", "connections", "status", "forms",
        "access", "authorizations", "extras", "notes",
    ]

    values = []
    for col in columns:
        val = member.get(col)
        if val is None:
            values.append("NULL")
        else:
            json_str = json.dumps(val, ensure_ascii=False)
            escaped = json_str.replace("'", "''")
            values.append(f"'{escaped}'::jsonb")

    cols_str = ", ".join(columns)
    vals_str = ",\n    ".join(values)
    return f"INSERT INTO member ({cols_str}) VALUES (\n    {vals_str}\n);"


def pick_membership_level(is_active: bool, is_new: bool) -> str:
    """Pick a membership level appropriate for the member's status."""
    if is_new:
        return "New Member"

    if not is_active:
        # Inactive members were on regular paid plans
        inactive_levels = [
            "Stripe Member - $65",
            "Member - Cash Payment",
            "Member - PayPal",
            "Member - Grandfathered Price",
            "Stripe Member w/ Storage - $95",
        ]
        return random.choice(inactive_levels)

    # Active members — weighted random from the full list
    types = list(MEMBERSHIP_WEIGHTS.keys())
    weights = [MEMBERSHIP_WEIGHTS[t] for t in types]
    return random.choices(types, weights=weights, k=1)[0]


def generate_forms(fake: Faker) -> dict:
    """Generate a realistic forms JSONB object."""
    waiver_date = fake.date_between(start_date="-5y", end_date="-1m")
    orientation_date = waiver_date + timedelta(days=random.randint(1, 14))
    return {
        "id_check_1": fake.state_abbr(),
        "id_check_2": f"DL-{random.randint(1000, 9999)}",
        "waiver_signed_date": waiver_date.isoformat(),
        "terms_of_use_accepted": "true",
        "essentials_form": "completed",
        "orientation_completed_date": orientation_date.isoformat(),
    }


def generate_unique_rfid_tags(count: int, used_tags: set) -> list[str]:
    """Generate unique RFID tags (10 digit numeric strings)."""
    tags = []
    for _ in range(count):
        for _attempt in range(1000):
            tag = str(random.randint(1000000000, 9999999999))
            if tag not in used_tags:
                used_tags.add(tag)
                tags.append(tag)
                break
    return tags


def generate_authorizations() -> dict | None:
    """Generate a random set of authorizations."""
    num_physical = random.choices(
        [0, 1, 2, 3, 5, 7, 10, 15],
        weights=[10, 15, 15, 15, 15, 10, 10, 5],
        k=1,
    )[0]
    num_computer = random.choices(
        [0, 0, 0, 1, 1, 2, 3, 4],
        weights=[30, 10, 10, 15, 10, 10, 10, 5],
        k=1,
    )[0]

    physical = sorted(random.sample(
        PHYSICAL_AUTHORIZATIONS,
        min(num_physical, len(PHYSICAL_AUTHORIZATIONS)),
    ))
    computer = sorted(random.sample(
        COMPUTER_AUTHORIZATIONS,
        min(num_computer, len(COMPUTER_AUTHORIZATIONS)),
    ))

    if not physical and not computer:
        return None

    result = {}
    if physical:
        result["authorizations"] = physical
    else:
        result["authorizations"] = []
    if computer:
        result["computer_authorizations"] = computer
    else:
        result["computer_authorizations"] = []
    return result


def generate_notes(fake: Faker) -> dict | None:
    """Generate random notes entries."""
    num_notes = random.randint(1, 3)
    notes_list = []
    for _ in range(num_notes):
        notes_list.append({
            "date": fake.date_between(start_date="-3y", end_date="today").isoformat(),
            "author": random.choice(["System", "Board", "Admin"]),
            "text": fake.sentence(nb_words=random.randint(5, 15)),
        })
    return {"notes": notes_list}


def generate_random_member(
    fake: Faker,
    used_rfid_tags: set,
    used_usernames: set,
    used_emails: set,
) -> dict:
    """Generate a single randomized member dict."""
    # ~80% Active, ~20% Inactive
    is_active = random.random() < 0.8

    # ~8% of active members are "brand new" (minimal data)
    is_new = is_active and random.random() < 0.08

    first_name = fake.first_name()
    last_name = fake.last_name()

    # Build a unique username
    username = f"{first_name[0].lower()}{last_name.lower()}"
    base_username = username
    counter = 1
    while username in used_usernames:
        username = f"{base_username}{counter}"
        counter += 1

    # Build a unique email
    email = f"{first_name.lower()}.{last_name.lower()}@example.com"
    base_email = email
    counter = 1
    while email in used_emails:
        email = f"{first_name.lower()}.{last_name.lower()}{counter}@example.com"
        counter += 1

    if not is_new:
        used_usernames.add(username)
    used_emails.add(email)

    # Identity
    identity = {
        "first_name": first_name,
        "last_name": last_name,
        "nickname": fake.user_name() if not is_new else None,
        "active_directory_username": username if not is_new else None,
        "emails": [{"type": "primary", "email_address": email}],
    }

    # Status
    membership_level = pick_membership_level(is_active, is_new)
    if is_new:
        member_since = fake.date_between(start_date="-14d", end_date="today").isoformat()
    elif is_active:
        member_since = fake.date_between(start_date="-7y", end_date="-2m").isoformat()
    else:
        member_since = fake.date_between(start_date="-8y", end_date="-1y").isoformat()

    status = {
        "membership_status": "Active" if is_active else "Inactive",
        "membership_level": membership_level,
        "member_since": member_since,
    }

    # Connections (~65% chance if not new)
    connections = None
    if not is_new and random.random() < 0.65:
        connections = {"discord_username": fake.user_name()}

    # Forms (null if brand new)
    forms = None if is_new else generate_forms(fake)

    # Access / RFID (null if brand new)
    access = None
    if not is_new:
        num_tags = random.choices([0, 1, 1, 1, 2, 2, 3], k=1)[0]
        if num_tags > 0:
            tags = generate_unique_rfid_tags(num_tags, used_rfid_tags)
            if tags:
                access = {"rfid_tags": tags}

    # Authorizations (null if brand new)
    authorizations = None if is_new else generate_authorizations()

    # Extras — storage for members with storage-type plans, or ~15% random
    extras = None
    if not is_new:
        has_storage_plan = "Storage" in membership_level
        if has_storage_plan or random.random() < 0.15:
            area = random.choice(STORAGE_AREAS)
            row_letter = random.choice("ABCDEFGH")
            slot_number = random.randint(1, 30)
            extras = {
                "storage_id": f"{row_letter}-{slot_number:02d}",
                "storage_area": area,
            }

    # Notes (~35% chance if not new)
    notes = None
    if not is_new and random.random() < 0.35:
        notes = generate_notes(fake)

    # Inactive members might have a lapsed note
    if not is_active and (notes is None or random.random() < 0.6):
        lapsed_note = {
            "date": fake.date_between(start_date="-6m", end_date="today").isoformat(),
            "author": "System",
            "text": random.choice([
                "Membership lapsed \u2014 moved to inactive",
                "Payment failed \u2014 membership deactivated",
                "Member requested deactivation",
                "Membership expired \u2014 no renewal",
            ]),
        }
        if notes is None:
            notes = {"notes": [lapsed_note]}
        else:
            notes["notes"].append(lapsed_note)

    return {
        "identity": identity,
        "connections": connections,
        "status": status,
        "forms": forms,
        "access": access,
        "authorizations": authorizations,
        "extras": extras,
        "notes": notes,
    }


### Role assignment SQL

ROLE_ASSIGNMENTS = [
    (2, 1, "Ada Lovelace", "Administrator"),
    (2, 2, "Charles Babbage", "Administrator"),
    (1, 3, "Nikola Tesla", "Authorizer"),
    (1, 4, "Hedy Lamarr", "Authorizer"),
    (3, 5, "Grace Hopper", "Board"),
    (3, 6, "Margaret Hamilton", "Board"),
]


def generate_role_assignments_sql() -> str:
    """Generate INSERT statements for member_to_role."""
    lines = []
    for role_id, member_id, name, role_name in ROLE_ASSIGNMENTS:
        lines.append(
            f"INSERT INTO member_to_role (role_id, member_id) "
            f"VALUES ({role_id}, {member_id});   "
            f"/* {name} -> {role_name} */"
        )
    return "\n".join(lines)


### Main SQL generation

def generate_sql(count: int, seed: str) -> str:
    """Generate the complete seed data SQL file."""
    # Convert seed string to integer for random/Faker seeding
    seed_int = int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16)
    random.seed(seed_int)
    Faker.seed(seed_int)
    fake = Faker()

    lines = []

    # Header
    lines.append("/*")
    lines.append(f" * Deep Harbor Seed Data (generated)")
    lines.append(f" *")
    lines.append(f" * Seed:  {seed}")
    lines.append(f" * Count: {count + len(DEV_USERS)} total ({len(DEV_USERS)} dev users + {count} random)")
    lines.append(f" *")
    lines.append(f" * Generated by: pg/tools/generate_seed_data.py")
    lines.append(f" * Reproduce with: uv run pg/tools/generate_seed_data.py --seed {seed} --count {count}")
    lines.append(f" *")
    lines.append(f" * IMPORTANT: The first {len(DEV_USERS)} members are dev bypass users with stable IDs.")
    lines.append(f" * Issue #13 (dev auth bypass) references these IDs. Don't reorder them.")
    lines.append(f" *")
    lines.append(f" * Inserting members fires the audit trigger, log_member_changes(),")
    lines.append(f" * and pg_notify. First boot will be noisy. This is expected.")
    lines.append(f" */")
    lines.append("")

    # Dev users
    lines.append("")
    lines.append("/* =====================================================")
    lines.append(f" * Dev Bypass Users (IDs 1-{len(DEV_USERS)})")
    lines.append(" * ===================================================== */")
    lines.append("")
    for i, user in enumerate(DEV_USERS):
        name = f"{user['identity']['first_name']} {user['identity']['last_name']}"
        lines.append(f"/* ID {i + 1} - {name} */")
        lines.append(make_member_sql(user))
        lines.append("")

    # Random members
    used_rfid_tags = set(DEV_USER_RFID_TAGS)
    used_usernames = set(DEV_USER_USERNAMES)
    used_emails = set(DEV_USER_EMAILS)

    start_id = len(DEV_USERS) + 1
    end_id = start_id + count - 1

    lines.append("")
    lines.append("/* =====================================================")
    lines.append(f" * Random Members (IDs {start_id}-{end_id})")
    lines.append(" * ===================================================== */")
    lines.append("")

    for i in range(count):
        member = generate_random_member(fake, used_rfid_tags, used_usernames, used_emails)
        name = f"{member['identity']['first_name']} {member['identity']['last_name']}"
        lines.append(f"/* ID {start_id + i} - {name} */")
        lines.append(make_member_sql(member))
        lines.append("")

    # Role assignments
    lines.append("")
    lines.append("/* =====================================================")
    lines.append(" * Role Assignments for Dev Bypass Users")
    lines.append(" * Roles: Authorizer (1), Administrator (2), Board (3)")
    lines.append(" * ===================================================== */")
    lines.append("")
    lines.append(generate_role_assignments_sql())
    lines.append("")

    # Sequence reset
    lines.append("")
    lines.append("/* Reset the member identity sequence to account for seed data */")
    lines.append("SELECT setval(pg_get_serial_sequence('member', 'id'), (SELECT MAX(id) FROM member));")
    lines.append("")

    return "\n".join(lines)


### CLI

def main():
    parser = argparse.ArgumentParser(
        description="Generate seed data SQL for the Deep Harbor CRM database.",
        epilog="Example: uv run pg/tools/generate_seed_data.py --seed abc123 --count 50",
    )
    parser.add_argument(
        "--seed",
        type=str,
        default=None,
        help="Seed for reproducible output. If omitted, a random seed is "
             "generated and printed to stderr.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=15,
        help="Number of ADDITIONAL random members beyond the 10 dev users "
             "(default: 15, for 25 total).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path. Defaults to stdout.",
    )

    args = parser.parse_args()

    seed = args.seed
    if seed is None:
        seed = secrets.token_hex(8)
        print(f"Generated seed: {seed}", file=sys.stderr)

    sql = generate_sql(args.count, seed)

    if args.output:
        with open(args.output, "w") as f:
            f.write(sql)
        print(f"Wrote {args.output} ({args.count + len(DEV_USERS)} members)", file=sys.stderr)
    else:
        print(sql)


if __name__ == "__main__":
    main()
