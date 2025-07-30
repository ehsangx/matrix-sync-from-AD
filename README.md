# Matrix AD Sync

A Python tool to synchronize Active Directory (LDAP) group members into specific rooms in a [Matrix Synapse](https://matrix.org) homeserver.

## ✨ Features

- Connects to AD via LDAP.
- Maps AD groups to specific Matrix room IDs.
- Automatically creates Matrix users if they don’t exist.
- Adds users to specified rooms using Synapse Admin API.
- Supports configuration via `groups.ini`.

## 🔧 Requirements

- Python 3.x
- Synapse installed with working Admin API
- A dedicated AD service account

## ⚙️ Configuration

Create a `groups.ini` file:

```ini
[Engineering]
room_id = !abc123:your-matrix-server.com
ad_group_dn = CN=engineering,OU=Groups,DC=yourdomain,DC=com
```

## 🚀 Run

```bash
python3 sync.py
```

## 🛡️ Security Note

Do **NOT** hardcode sensitive data. Use environment variables like:

```bash
export MATRIX_ADMIN_TOKEN=...
export LDAP_PASSWORD=...
```
