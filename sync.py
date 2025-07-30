import ldap
import requests
import json
import configparser
import os
import subprocess

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'groups.ini')

# Environment-based sensitive config
REGISTER_SCRIPT_PATH = os.getenv("REGISTER_SCRIPT_PATH", "/opt/venvs/matrix-synapse/bin/register_new_matrix_user")
HOMESERVER_CONFIG_PATH = os.getenv("HOMESERVER_CONFIG_PATH", "/etc/matrix-synapse/homeserver.yaml")

SYNAPSE_URL = os.getenv("SYNAPSE_URL", "http://127.0.0.1:8008")
ADMIN_TOKEN = os.getenv("MATRIX_ADMIN_TOKEN", "")
SERVER_NAME = os.getenv("MATRIX_SERVER_NAME", "matrix.example.com")

LDAP_URI = os.getenv("LDAP_URI", "ldap://your-ldap-server")
LDAP_BIND_DN = os.getenv("LDAP_BIND_DN", "")
LDAP_BIND_PASSWORD = os.getenv("LDAP_PASSWORD", "")
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "")

def get_ad_group_members(group_dn):
    members = []
    try:
        con = ldap.initialize(LDAP_URI)
        con.set_option(ldap.OPT_REFERRALS, 0)
        con.set_option(ldap.OPT_NETWORK_TIMEOUT, 10.0)
        con.simple_bind_s(LDAP_BIND_DN, LDAP_BIND_PASSWORD)
        search_filter = f"(&(objectClass=person)(memberOf={group_dn}))"
        attributes = ['sAMAccountName']
        results = con.search_s(LDAP_BASE_DN, ldap.SCOPE_SUBTREE, search_filter, attributes)
        for dn, entry in results:
            if 'sAMAccountName' in entry:
                members.append(entry['sAMAccountName'][0].decode('utf-8').lower())
    except ldap.LDAPError as e:
        print(f"LDAP Error for group {group_dn}: {e}")
    finally:
        if 'con' in locals():
            con.unbind_s()
    return members

def create_matrix_user(user_localpart):
    print(f"Attempting to create user @{user_localpart}:{SERVER_NAME} via script...")
    temp_password = "unused-random-password"
    command = [
        REGISTER_SCRIPT_PATH,
        '-u', user_localpart,
        '-p', temp_password,
        '--no-admin',
        '-c', HOMESERVER_CONFIG_PATH
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            print(f"Successfully created user {user_localpart}")
        elif "User ID already taken" in result.stderr:
            print(f"User {user_localpart} already exists.")
        else:
            print(f"Failed to create user {user_localpart}. STDOUT: [{result.stdout.strip()}] STDERR: [{result.stderr.strip()}]")
    except FileNotFoundError:
        print(f"ERROR: Script not found at '{REGISTER_SCRIPT_PATH}'. Please check the path.")
    except Exception as e:
        print(f"Unexpected error: {e}")

def get_matrix_room_members(room_id):
    members = []
    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    url = f"{SYNAPSE_URL}/_synapse/admin/v1/rooms/{room_id}/members"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        for user_id in data['members']:
            if user_id.endswith(f":{SERVER_NAME}"):
                localpart = user_id.split(':')[0][1:]
                members.append(localpart)
    except requests.exceptions.RequestException as e:
        print(f"Matrix API Error for room {room_id}: {e}")
    return members

def join_user_to_room(user_localpart, room_id):
    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}', 'Content-Type': 'application/json'}
    user_id = f"@{user_localpart}:{SERVER_NAME}"
    url = f"{SYNAPSE_URL}/_synapse/admin/v1/join/{room_id}"
    payload = {"user_id": user_id}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            print(f"Joined {user_id} to {room_id}")
        else:
            print(f"Failed to join {user_id}: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Join error: {e}")

def main():
    if not ADMIN_TOKEN:
        print("ERROR: MATRIX_ADMIN_TOKEN is not set.")
        return

    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    print("Starting AD to Matrix sync...")

    for section in config.sections():
        print(f"\n--- Syncing Group: {section} ---")
        try:
            room_id = config[section]['room_id']
            group_dn = config[section]['ad_group_dn']
        except KeyError as e:
            print(f"Missing key in section {section}: {e}")
            continue

        if "REPLACE_WITH" in room_id:
            print(f"Skipping section {section}, room_id is not set.")
            continue

        ad_members = get_ad_group_members(group_dn)
        matrix_members = get_matrix_room_members(room_id)

        if not ad_members and not matrix_members:
            print("Could not fetch members.")
            continue

        users_to_add = set(ad_members) - set(matrix_members)
        if not users_to_add:
            print("Room already in sync.")
        else:
            for user in users_to_add:
                create_matrix_user(user)
                join_user_to_room(user, room_id)

    print("\nSync complete.")

if __name__ == "__main__":
    main()
