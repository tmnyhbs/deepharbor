/*
 * Deep Harbor Seed Data
 *
 * This file populates the database with ~25 fictional members for
 * local development and testing. It runs as 02-seed_data.sql during
 * Docker first-boot init, after the schema (01-pgsql_schema.sql)
 * is already in place.
 *
 * IMPORTANT: The first 10 members are "dev bypass" users with stable,
 * predictable IDs (1-10). Issue #13 (dev auth bypass) references
 * these IDs directly. Don't reorder them.
 *
 * Inserting members fires the audit trigger, log_member_changes(),
 * and pg_notify. First boot will be noisy as the dispatcher processes
 * ~25 change events. This is expected and harmless with DEV_MODE=true
 * on the worker services.
 */


/* =====================================================================
 * Dev Bypass Users (IDs 1-10)
 *
 * These are inserted first so their IDs are predictable. Each pair
 * serves a specific role in the dev auth bypass:
 *   IDs 1-2:  Administrators (role_id=2)
 *   IDs 3-4:  Authorizers    (role_id=1)
 *   IDs 5-6:  Board members  (role_id=3)
 *   IDs 7-8:  Active members (no role)
 *   IDs 9-10: Inactive members (no role)
 * ===================================================================== */

/* ID 1 - Ada Lovelace, Administrator
 * Well-populated active member with lots of data — good for testing
 * the admin portal with a full member record.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Ada", "last_name": "Lovelace", "nickname": "enchantress_of_numbers", "active_directory_username": "alovelace", "emails": [{"type": "primary", "email_address": "ada.lovelace@example.com"}]}'::jsonb,
    '{"discord_username": "ada_admin"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Stripe Member - $65", "member_since": "2020-01-15"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-1234", "waiver_signed_date": "2020-01-15", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2020-01-22"}'::jsonb,
    '{"rfid_tags": ["12345678", "87654321"]}'::jsonb,
    '{"authorizations": ["Table Saw", "Band Saw", "Mig Welders", "Tig Welders", "Jointer", "Planer", "Mitre Saw", "Sanders", "Wood Drill Press", "Router Table"], "computer_authorizations": ["Epilog Authorized Users", "Tormach Authorized Users", "ShopBot Authorized Users"]}'::jsonb,
    '{"storage_id": "A-01", "storage_area": "North Wall"}'::jsonb,
    '{"notes": [{"date": "2020-01-22", "author": "System", "text": "Completed orientation and safety training"}, {"date": "2023-06-10", "author": "Board", "text": "Granted administrator access to the admin portal"}]}'::jsonb
);

/* ID 2 - Charles Babbage, Administrator
 * Another admin with slightly different data — useful for testing
 * multi-admin scenarios.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Charles", "last_name": "Babbage", "nickname": "difference_engine", "active_directory_username": "cbabbage", "emails": [{"type": "primary", "email_address": "charles.babbage@example.com"}]}'::jsonb,
    '{"discord_username": "cbabbage"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Member - Cash Payment", "member_since": "2019-03-10"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-5678", "waiver_signed_date": "2019-03-10", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2019-03-17"}'::jsonb,
    '{"rfid_tags": ["23456789"]}'::jsonb,
    '{"authorizations": ["Table Saw", "Band Saw", "Metal Band Saw", "Metal Drill Press", "Bridgeport Mill", "Clausing Lathe"], "computer_authorizations": ["Boss Authorized Users", "CNC Plasma Authorized Users"]}'::jsonb,
    NULL,
    '{"notes": [{"date": "2019-03-17", "author": "System", "text": "Orientation completed"}, {"date": "2024-01-15", "author": "Board", "text": "Added as administrator"}]}'::jsonb
);

/* ID 3 - Nikola Tesla, Authorizer
 * Heavy on authorizations — this is someone who trains others on
 * equipment, so they should have auths on most things.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Nikola", "last_name": "Tesla", "nickname": "spark_lord", "active_directory_username": "ntesla", "emails": [{"type": "primary", "email_address": "nikola.tesla@example.com"}]}'::jsonb,
    '{"discord_username": "spark_lord"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Volunteer", "member_since": "2018-06-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "PP-9012", "waiver_signed_date": "2018-06-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2018-06-08"}'::jsonb,
    '{"rfid_tags": ["11223344"]}'::jsonb,
    '{"authorizations": ["Table Saw", "Band Saw", "Mig Welders", "Tig Welders", "Jointer", "Planer", "Mitre Saw", "Sanders", "Wood Drill Press", "Router Table", "Metal Band Saw", "Metal Drill Press", "Bridgeport Mill", "Clausing Lathe", "LeBlond Lathe", "Surface Grinder", "Hand held plasma cutter", "Pneumatic Power Tools", "Powder Coating Equipment", "Tube Bending Equipment"], "computer_authorizations": ["Epilog Authorized Users", "Tormach Authorized Users", "Universal Authorized Users", "Boss Authorized Users", "CNC Plasma Authorized Users", "ShopBot Authorized Users"]}'::jsonb,
    NULL,
    '{"notes": [{"date": "2018-06-08", "author": "System", "text": "Completed orientation"}, {"date": "2019-02-14", "author": "Board", "text": "Approved as equipment authorizer for metalworking and CNC areas"}]}'::jsonb
);

/* ID 4 - Hedy Lamarr, Authorizer
 * Another authorizer, focused on different equipment areas.
 * Has storage because she''s a volunteer with free storage.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Hedy", "last_name": "Lamarr", "nickname": "frequency_hopper", "active_directory_username": "hlamarr", "emails": [{"type": "primary", "email_address": "hedy.lamarr@example.com"}]}'::jsonb,
    '{"discord_username": "hedy_builds"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Volunteer w/ Free Storage", "member_since": "2019-09-15"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-3456", "waiver_signed_date": "2019-09-15", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2019-09-22"}'::jsonb,
    '{"rfid_tags": ["44556677", "55667788"]}'::jsonb,
    '{"authorizations": ["Table Saw", "Band Saw", "Wood Lathe", "Wood Mini Lathe", "Drum Sander", "Panel Saw", "Saw Dado", "Square Chisel Morticer", "Jointer", "Planer", "Ender 3D Printers", "Prusa 3D printers", "Formlabs Form 3 printer"], "computer_authorizations": ["Epilog Authorized Users", "Universal Authorized Users", "Vinyl Cutter Authorized Users", "Mimaki CJV30 printer Users"]}'::jsonb,
    '{"storage_id": "C-05", "storage_area": "Woodshop Corner"}'::jsonb,
    '{"notes": [{"date": "2019-09-22", "author": "System", "text": "Completed orientation and all woodshop authorizations"}, {"date": "2020-04-01", "author": "Board", "text": "Approved as authorizer for woodshop, 3D printing, and laser areas"}]}'::jsonb
);

/* ID 5 - Grace Hopper, Board Member
 * Board member with basic authorizations — she''s more of a
 * governance person than a shop user.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Grace", "last_name": "Hopper", "nickname": "queen_bug", "active_directory_username": "ghopper", "emails": [{"type": "primary", "email_address": "grace.hopper@example.com"}]}'::jsonb,
    '{"discord_username": "admiral_grace"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Board Member / Officer", "member_since": "2017-11-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-7890", "waiver_signed_date": "2017-11-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2017-11-08"}'::jsonb,
    '{"rfid_tags": ["99887766"]}'::jsonb,
    '{"authorizations": ["Ender 3D Printers", "Prusa 3D printers", "Band Saw"], "computer_authorizations": []}'::jsonb,
    NULL,
    '{"notes": [{"date": "2017-11-08", "author": "System", "text": "Completed orientation"}, {"date": "2022-01-01", "author": "Board", "text": "Elected to board of directors"}]}'::jsonb
);

/* ID 6 - Margaret Hamilton, Board Member
 * Another board member. Has a bit more shop experience.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Margaret", "last_name": "Hamilton", "nickname": "stack_overflow", "active_directory_username": "mhamilton", "emails": [{"type": "primary", "email_address": "margaret.hamilton@example.com"}]}'::jsonb,
    '{"discord_username": "mhamilton_apollo"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Board Member / Officer", "member_since": "2018-03-15"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-2345", "waiver_signed_date": "2018-03-15", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2018-03-22"}'::jsonb,
    '{"rfid_tags": ["77665544"]}'::jsonb,
    '{"authorizations": ["Table Saw", "Mitre Saw", "Sanders", "Ender 3D Printers"], "computer_authorizations": ["Epilog Authorized Users"]}'::jsonb,
    NULL,
    '{"notes": [{"date": "2018-03-22", "author": "System", "text": "Completed orientation"}, {"date": "2023-01-01", "author": "Board", "text": "Elected to board"}]}'::jsonb
);

/* ID 7 - Rosalind Franklin, Active Member
 * Well-populated active member with storage — good for testing
 * the member portal with a full member record.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Rosalind", "last_name": "Franklin", "nickname": "photo_51", "active_directory_username": "rfranklin", "emails": [{"type": "primary", "email_address": "rosalind.franklin@example.com"}]}'::jsonb,
    '{"discord_username": "xray_rosalind"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Member - Cash Payment", "member_since": "2021-04-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-6789", "waiver_signed_date": "2021-04-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2021-04-08"}'::jsonb,
    '{"rfid_tags": ["33221100", "44332211"]}'::jsonb,
    '{"authorizations": ["Table Saw", "Band Saw", "Mig Welders", "Jointer", "Planer", "Ender 3D Printers", "Prusa 3D printers"], "computer_authorizations": ["Epilog Authorized Users", "Tormach Authorized Users"]}'::jsonb,
    '{"storage_id": "B-12", "storage_area": "South Wall"}'::jsonb,
    '{"notes": [{"date": "2021-04-08", "author": "System", "text": "Completed orientation and basic woodshop training"}]}'::jsonb
);

/* ID 8 - Katherine Johnson, Active Member
 * Another well-populated active member — different set of auths.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Katherine", "last_name": "Johnson", "nickname": "human_computer", "active_directory_username": "kjohnson", "emails": [{"type": "primary", "email_address": "katherine.johnson@example.com"}]}'::jsonb,
    '{"discord_username": "kjohnson_math"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Stripe Member - $65", "member_since": "2022-02-14"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-0123", "waiver_signed_date": "2022-02-14", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2022-02-21"}'::jsonb,
    '{"rfid_tags": ["66778899"]}'::jsonb,
    '{"authorizations": ["Ender 3D Printers", "Prusa 3D printers", "Formlabs Form 3 printer", "Tier one Sewing Machine", "Serger sewing machine", "Button sewing machines"], "computer_authorizations": ["Epilog Authorized Users", "Vinyl Cutter Authorized Users"]}'::jsonb,
    NULL,
    '{"notes": [{"date": "2022-02-21", "author": "System", "text": "Completed orientation, focused on textiles and 3D printing"}]}'::jsonb
);

/* ID 9 - Marie Curie, Inactive Member
 * Former active member who let their membership lapse. Still has
 * data on record from when they were active.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Marie", "last_name": "Curie", "nickname": "glow_girl", "active_directory_username": "mcurie", "emails": [{"type": "primary", "email_address": "marie.curie@example.com"}]}'::jsonb,
    '{"discord_username": "mcurie_rad"}'::jsonb,
    '{"membership_status": "Inactive", "membership_level": "Member - Cash Payment", "member_since": "2018-06-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-4567", "waiver_signed_date": "2018-06-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2018-06-08"}'::jsonb,
    '{"rfid_tags": ["33445566"]}'::jsonb,
    '{"authorizations": ["Table Saw", "Band Saw", "Mig Welders", "Cold Metals Basic"], "computer_authorizations": []}'::jsonb,
    NULL,
    '{"notes": [{"date": "2018-06-08", "author": "System", "text": "Completed orientation"}, {"date": "2024-03-01", "author": "System", "text": "Membership lapsed — moved to inactive"}]}'::jsonb
);

/* ID 10 - Laika Sputnik, Inactive Member
 * Another inactive member. This one has less data — they
 * were only a member briefly.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Laika", "last_name": "Sputnik", "nickname": "good_dog", "active_directory_username": "lsputnik", "emails": [{"type": "primary", "email_address": "laika.sputnik@example.com"}]}'::jsonb,
    NULL,
    '{"membership_status": "Inactive", "membership_level": "Stripe Member - $65", "member_since": "2023-09-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-8901", "waiver_signed_date": "2023-09-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2023-09-08"}'::jsonb,
    NULL,
    '{"authorizations": ["Band Saw", "Ender 3D Printers"], "computer_authorizations": []}'::jsonb,
    NULL,
    '{"notes": [{"date": "2023-09-08", "author": "System", "text": "Completed orientation"}, {"date": "2024-06-01", "author": "System", "text": "Membership lapsed after 9 months"}]}'::jsonb
);


/* =====================================================================
 * Additional Members (IDs 11-25)
 *
 * These round out the seed data with a mix of membership levels,
 * authorization counts, and data completeness. Famous scientists,
 * engineers, and inventors — all fictional usage, @example.com emails.
 * ===================================================================== */

/* ID 11 - Wernher von Braun, Area Host
 * Long-time member who hosts the metalworking area. Tons of auths.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Wernher", "last_name": "Von Braun", "nickname": "rocket_man", "active_directory_username": "wvonbraun", "emails": [{"type": "primary", "email_address": "wernher.vonbraun@example.com"}]}'::jsonb,
    '{"discord_username": "rocketman_w"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Area Host", "member_since": "2017-01-15"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-1111", "waiver_signed_date": "2017-01-15", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2017-01-22"}'::jsonb,
    '{"rfid_tags": ["10203040", "50607080"]}'::jsonb,
    '{"authorizations": ["Table Saw", "Band Saw", "Mig Welders", "Tig Welders", "Metal Band Saw", "Metal Drill Press", "Bridgeport Mill", "Clausing Lathe", "LeBlond Lathe", "Surface Grinder", "Hand held plasma cutter", "Pneumatic Power Tools", "Powder Coating Equipment", "Tube Bending Equipment", "Cold Metals Basic"], "computer_authorizations": ["Boss Authorized Users", "CNC Plasma Authorized Users", "Tormach Authorized Users"]}'::jsonb,
    NULL,
    '{"notes": [{"date": "2017-01-22", "author": "System", "text": "Completed orientation"}, {"date": "2018-05-01", "author": "Board", "text": "Appointed area host for metalworking"}]}'::jsonb
);

/* ID 12 - Emmy Noether, Stripe Member w/ Storage
 * Active member with storage who does a lot of woodworking and 3D printing.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Emmy", "last_name": "Noether", "nickname": "symmetry_queen", "active_directory_username": "enoether", "emails": [{"type": "primary", "email_address": "emmy.noether@example.com"}]}'::jsonb,
    '{"discord_username": "emmy_makes"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Stripe Member w/ Storage - $95", "member_since": "2021-08-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-2222", "waiver_signed_date": "2021-08-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2021-08-08"}'::jsonb,
    '{"rfid_tags": ["11112222", "33334444", "55556666"]}'::jsonb,
    '{"authorizations": ["Table Saw", "Band Saw", "Jointer", "Planer", "Mitre Saw", "Router Table", "Wood Lathe", "Drum Sander", "Panel Saw", "Ender 3D Printers", "Prusa 3D printers", "Formlabs Form 3 printer"], "computer_authorizations": ["Epilog Authorized Users", "Universal Authorized Users", "ShopBot Authorized Users"]}'::jsonb,
    '{"storage_id": "D-08", "storage_area": "East Wall"}'::jsonb,
    NULL
);

/* ID 13 - Richard Feynman, Member - Grandfathered Price
 * Long-time member still on the old pricing. Mostly does electronics.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Richard", "last_name": "Feynman", "nickname": "surely_joking", "active_directory_username": "rfeynman", "emails": [{"type": "primary", "email_address": "richard.feynman@example.com"}]}'::jsonb,
    '{"discord_username": "feynman_diagrams"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Member - Grandfathered Price", "member_since": "2016-05-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-3333", "waiver_signed_date": "2016-05-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2016-05-08"}'::jsonb,
    '{"rfid_tags": ["77778888"]}'::jsonb,
    '{"authorizations": ["Ender 3D Printers", "Band Saw", "Sanders"], "computer_authorizations": []}'::jsonb,
    NULL,
    '{"notes": [{"date": "2016-05-08", "author": "System", "text": "Completed orientation — mostly interested in electronics bench"}]}'::jsonb
);

/* ID 14 - Barbara McClintock, Scholarship Member
 * Scholarship member who''s been getting into more shop equipment.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Barbara", "last_name": "McClintock", "nickname": "jumping_genes", "active_directory_username": "bmcclintock", "emails": [{"type": "primary", "email_address": "barbara.mcclintock@example.com"}]}'::jsonb,
    '{"discord_username": "barb_bio"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Scholarship", "member_since": "2024-01-15"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-4444", "waiver_signed_date": "2024-01-15", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2024-01-22"}'::jsonb,
    '{"rfid_tags": ["99990000"]}'::jsonb,
    '{"authorizations": ["Band Saw", "Ender 3D Printers", "Tier one Sewing Machine"], "computer_authorizations": []}'::jsonb,
    NULL,
    '{"notes": [{"date": "2024-01-22", "author": "System", "text": "Completed orientation"}, {"date": "2024-01-15", "author": "Board", "text": "Approved scholarship membership"}]}'::jsonb
);

/* ID 15 - Guglielmo Marconi, Stripe Volunteer w/ Paid Storage
 * Volunteer who helps with the radio and electronics area.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Guglielmo", "last_name": "Marconi", "nickname": "radio_wave", "active_directory_username": "gmarconi", "emails": [{"type": "primary", "email_address": "guglielmo.marconi@example.com"}]}'::jsonb,
    '{"discord_username": "marconi_radio"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Stripe Volunteer w/ Paid Storage - $30", "member_since": "2020-07-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-5555", "waiver_signed_date": "2020-07-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2020-07-08"}'::jsonb,
    '{"rfid_tags": ["12121212"]}'::jsonb,
    '{"authorizations": ["Band Saw", "Sanders", "Ender 3D Printers", "Cold Metals Basic"], "computer_authorizations": []}'::jsonb,
    '{"storage_id": "E-03", "storage_area": "Electronics Bench"}'::jsonb,
    NULL
);

/* ID 16 - Dorothy Vaughan, New Member (brand new)
 * Just signed up — barely anything filled in yet. Good for testing
 * the new member experience.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Dorothy", "last_name": "Vaughan", "nickname": null, "active_directory_username": null, "emails": [{"type": "primary", "email_address": "dorothy.vaughan@example.com"}]}'::jsonb,
    NULL,
    '{"membership_status": "Active", "membership_level": "New Member", "member_since": "2026-02-10"}'::jsonb,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
);

/* ID 17 - James Watt, Member w/ Storage - Cash Payment
 * Does a lot of metalworking. Has storage for ongoing projects.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "James", "last_name": "Watt", "nickname": "steam_power", "active_directory_username": "jwatt", "emails": [{"type": "primary", "email_address": "james.watt@example.com"}]}'::jsonb,
    '{"discord_username": "jwatt_steam"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Member w/ Storage - Cash Payment", "member_since": "2019-11-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-6666", "waiver_signed_date": "2019-11-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2019-11-08"}'::jsonb,
    '{"rfid_tags": ["34343434"]}'::jsonb,
    '{"authorizations": ["Table Saw", "Band Saw", "Mig Welders", "Tig Welders", "Metal Band Saw", "Metal Drill Press", "Bridgeport Mill", "Blacksmithing"], "computer_authorizations": ["CNC Plasma Authorized Users"]}'::jsonb,
    '{"storage_id": "F-15", "storage_area": "Metalshop"}'::jsonb,
    NULL
);

/* ID 18 - Chien-Shiung Wu, Member - PayPal
 * Active member, pays via PayPal. Mix of auths.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Chien-Shiung", "last_name": "Wu", "nickname": "first_lady_of_physics", "active_directory_username": "cwu", "emails": [{"type": "primary", "email_address": "chienshiung.wu@example.com"}]}'::jsonb,
    '{"discord_username": "cswu_physics"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Member - PayPal", "member_since": "2022-09-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-7777", "waiver_signed_date": "2022-09-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2022-09-08"}'::jsonb,
    '{"rfid_tags": ["56565656"]}'::jsonb,
    '{"authorizations": ["Ender 3D Printers", "Prusa 3D printers", "Band Saw", "Table Saw", "Mitre Saw"], "computer_authorizations": ["Epilog Authorized Users"]}'::jsonb,
    NULL,
    NULL
);

/* ID 19 - Buckminster Fuller, Stripe Member - $65
 * Geodesic dome enthusiast. Mostly woodworking auths.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Buckminster", "last_name": "Fuller", "nickname": "bucky_ball", "active_directory_username": "bfuller", "emails": [{"type": "primary", "email_address": "buckminster.fuller@example.com"}]}'::jsonb,
    '{"discord_username": "bucky_dome"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Stripe Member - $65", "member_since": "2023-03-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-8888", "waiver_signed_date": "2023-03-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2023-03-08"}'::jsonb,
    '{"rfid_tags": ["78787878"]}'::jsonb,
    '{"authorizations": ["Table Saw", "Band Saw", "Jointer", "Planer", "Mitre Saw", "Router Table", "Wood Drill Press", "Multi-Router", "Panel Saw"], "computer_authorizations": ["ShopBot Authorized Users"]}'::jsonb,
    NULL,
    NULL
);

/* ID 20 - Rachel Carson, Contractor
 * Active contractor — limited time engagement.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Rachel", "last_name": "Carson", "nickname": "silent_spring", "active_directory_username": "rcarson", "emails": [{"type": "primary", "email_address": "rachel.carson@example.com"}]}'::jsonb,
    NULL,
    '{"membership_status": "Active", "membership_level": "Contractor", "member_since": "2025-06-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-9999", "waiver_signed_date": "2025-06-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2025-06-08"}'::jsonb,
    '{"rfid_tags": ["90909090"]}'::jsonb,
    '{"authorizations": ["Band Saw", "Sanders"], "computer_authorizations": []}'::jsonb,
    NULL,
    '{"notes": [{"date": "2025-06-01", "author": "Board", "text": "Contractor engagement for building renovation project"}]}'::jsonb
);

/* ID 21 - Philo Farnsworth, Member w/ Storage - Grandfathered Price
 * Long-time member on grandfathered pricing with storage.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Philo", "last_name": "Farnsworth", "nickname": "tv_inventor", "active_directory_username": "pfarnsworth", "emails": [{"type": "primary", "email_address": "philo.farnsworth@example.com"}]}'::jsonb,
    '{"discord_username": "philo_tv"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Member w/ Storage - Grandfathered Price", "member_since": "2016-09-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-1010", "waiver_signed_date": "2016-09-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2016-09-08"}'::jsonb,
    '{"rfid_tags": ["21212121"]}'::jsonb,
    '{"authorizations": ["Band Saw", "Table Saw", "Ender 3D Printers", "Sanders", "Wood Drill Press", "Cold Metals Basic", "Coffee Roaster"], "computer_authorizations": []}'::jsonb,
    '{"storage_id": "A-22", "storage_area": "North Wall"}'::jsonb,
    NULL
);

/* ID 22 - Jocelyn Bell Burnell, Volunteer w/ Paid Storage
 * Volunteer who helps with outreach. Has storage for teaching materials.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Jocelyn", "last_name": "Bell Burnell", "nickname": "pulsar_finder", "active_directory_username": "jbellburnell", "emails": [{"type": "primary", "email_address": "jocelyn.bellburnell@example.com"}]}'::jsonb,
    '{"discord_username": "jocelyn_stars"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Volunteer w/ Paid Storage", "member_since": "2021-01-15"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-1212", "waiver_signed_date": "2021-01-15", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2021-01-22"}'::jsonb,
    '{"rfid_tags": ["43434343"]}'::jsonb,
    '{"authorizations": ["Ender 3D Printers", "Prusa 3D printers", "Band Saw", "Tier one Sewing Machine", "Billiards"], "computer_authorizations": ["Epilog Authorized Users"]}'::jsonb,
    '{"storage_id": "G-01", "storage_area": "Classroom"}'::jsonb,
    '{"notes": [{"date": "2021-02-01", "author": "Board", "text": "Volunteering to run monthly intro-to-science workshops for kids"}]}'::jsonb
);

/* ID 23 - Dmitri Mendeleev, Inactive - Member - Grandfathered Price
 * Was on grandfathered pricing for a long time. Moved away.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Dmitri", "last_name": "Mendeleev", "nickname": "periodic_table", "active_directory_username": "dmendeleev", "emails": [{"type": "primary", "email_address": "dmitri.mendeleev@example.com"}]}'::jsonb,
    '{"discord_username": "element118"}'::jsonb,
    '{"membership_status": "Inactive", "membership_level": "Member - Grandfathered Price", "member_since": "2015-03-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-1313", "waiver_signed_date": "2015-03-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2015-03-08"}'::jsonb,
    '{"rfid_tags": ["65656565"]}'::jsonb,
    '{"authorizations": ["Table Saw", "Band Saw", "Mig Welders", "Metal Band Saw", "Blacksmithing"], "computer_authorizations": []}'::jsonb,
    NULL,
    '{"notes": [{"date": "2015-03-08", "author": "System", "text": "Completed orientation"}, {"date": "2024-09-01", "author": "System", "text": "Membership lapsed — member relocated out of state"}]}'::jsonb
);

/* ID 24 - Michael Faraday, Inactive - Member - PayPal
 * Former PayPal member. Expired after a year.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "Michael", "last_name": "Faraday", "nickname": "field_lines", "active_directory_username": "mfaraday", "emails": [{"type": "primary", "email_address": "michael.faraday@example.com"}]}'::jsonb,
    NULL,
    '{"membership_status": "Inactive", "membership_level": "Member - PayPal", "member_since": "2022-05-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-1414", "waiver_signed_date": "2022-05-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2022-05-08"}'::jsonb,
    NULL,
    '{"authorizations": ["Band Saw", "Ender 3D Printers", "Sanders"], "computer_authorizations": []}'::jsonb,
    NULL,
    '{"notes": [{"date": "2023-05-01", "author": "System", "text": "PayPal subscription expired — moved to inactive"}]}'::jsonb
);

/* ID 25 - George Washington Carver, Member w/ Storage - PayPal
 * Active member with PayPal storage plan. Into woodworking and textiles.
 */
INSERT INTO member (identity, connections, status, forms, access, authorizations, extras, notes) VALUES (
    '{"first_name": "George Washington", "last_name": "Carver", "nickname": "peanut_wizard", "active_directory_username": "gwcarver", "emails": [{"type": "primary", "email_address": "george.carver@example.com"}]}'::jsonb,
    '{"discord_username": "gwcarver_makes"}'::jsonb,
    '{"membership_status": "Active", "membership_level": "Member w/ Storage - PayPal", "member_since": "2020-10-01"}'::jsonb,
    '{"id_check_1": "IL", "id_check_2": "DL-1515", "waiver_signed_date": "2020-10-01", "terms_of_use_accepted": "true", "essentials_form": "completed", "orientation_completed_date": "2020-10-08"}'::jsonb,
    '{"rfid_tags": ["87878787"]}'::jsonb,
    '{"authorizations": ["Table Saw", "Band Saw", "Jointer", "Planer", "Wood Lathe", "Tier one Sewing Machine", "Serger sewing machine", "Button sewing machines", "Saw Dado"], "computer_authorizations": ["Vinyl Cutter Authorized Users", "Mimaki CJV30 printer Users"]}'::jsonb,
    '{"storage_id": "B-07", "storage_area": "South Wall"}'::jsonb,
    NULL
);


/* =====================================================================
 * Role Assignments for Dev Bypass Users
 *
 * Roles: Authorizer (1), Administrator (2), Board (3)
 * These are referenced by the dev auth bypass (issue #13) so the
 * dev login page can show role-appropriate options.
 * ===================================================================== */

INSERT INTO member_to_role (role_id, member_id) VALUES (2, 1);   /* Ada Lovelace -> Administrator */
INSERT INTO member_to_role (role_id, member_id) VALUES (2, 2);   /* Charles Babbage -> Administrator */
INSERT INTO member_to_role (role_id, member_id) VALUES (1, 3);   /* Nikola Tesla -> Authorizer */
INSERT INTO member_to_role (role_id, member_id) VALUES (1, 4);   /* Hedy Lamarr -> Authorizer */
INSERT INTO member_to_role (role_id, member_id) VALUES (3, 5);   /* Grace Hopper -> Board */
INSERT INTO member_to_role (role_id, member_id) VALUES (3, 6);   /* Margaret Hamilton -> Board */


/* Reset the member identity sequence to account for seed data.
 * This ensures that any members created at runtime start with
 * IDs after the seed data range.
 */
SELECT setval(pg_get_serial_sequence('member', 'id'), (SELECT MAX(id) FROM member));

/* That's all the seed data! On first boot the dispatcher will
 * process the ~25 member_changes records created by the insert
 * triggers. With DEV_MODE=true on the worker services, these
 * will be handled gracefully without trying to talk to hardware.
 */
