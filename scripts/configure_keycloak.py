import time
import requests
import os
import json

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL_INTERNAL", "http://localhost:8080")
ADMIN_USER = "admin"
ADMIN_PASS = "admin"
REALM = "reports-realm"
TOKEN_URL = f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token"

def get_admin_token():
    data = {
        "username": ADMIN_USER,
        "password": ADMIN_PASS,
        "grant_type": "password",
        "client_id": "admin-cli"
    }
    r = requests.post(TOKEN_URL, data=data)
    if r.status_code != 200:
        print(f"Failed to get token: {r.status_code} {r.text}")
    r.raise_for_status()
    return r.json()["access_token"]

def main():
    print(f"Connecting to Keycloak at {KEYCLOAK_URL}...")
    token = None
    for i in range(30):
        try:
            token = get_admin_token()
            print("Connected!")
            break
        except Exception as e:
            print(f"Waiting for Keycloak... ({e})")
            time.sleep(2)

    if not token:
        print("Could not connect to Keycloak")
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 0. Update Realm Settings (Task 3: Access Token Lifespan <= 2 min)
    print("Updating Realm Token Lifespan to 120 seconds...")
    realm_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}"
    res = requests.put(realm_url, json={"accessTokenLifespan": 120}, headers=headers)
    if res.status_code < 300:
        print("Realm token lifespan updated.")
    else:
        print(f"Failed to update realm: {res.text}")

    # 1. Update Client (Task 2 & 3 support)
    print("Updating Client 'reports-frontend'...")
    clients_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients"
    r = requests.get(clients_url, params={"clientId": "reports-frontend"}, headers=headers)
    if r.status_code == 200 and len(r.json()) > 0:
        client_data = r.json()[0]
        client_id = client_data["id"]

        update_data = client_data.copy()
        update_data.update({
            "publicClient": False,
            "standardFlowEnabled": True,
            "directAccessGrantsEnabled": False,
            "implicitFlowEnabled": False,
            "clientAuthenticatorType": "client-secret",
            "secret": "secret",
            "redirectUris": ["http://localhost:8000/callback"],
            "attributes": {
                "pkce.code.challenge.method": "S256"
            }
        })

        # Keycloak API sometimes complains if you send back read-only fields, but usually ignores them.
        # Minimal update is safer if partial update supported, but Client update is usually full PUT.

        res = requests.put(f"{clients_url}/{client_id}", json=update_data, headers=headers)
        if res.status_code >= 200 and res.status_code < 300:
            print("Client updated successfully.")
        else:
            print(f"Failed to update client: {res.status_code} {res.text}")
    else:
        print("Client 'reports-frontend' not found.")

    # 2. Add LDAP (Task 4)
    print("Adding LDAP Provider...")
    components_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/components"
    r = requests.get(components_url, params={"parent": REALM, "type": "org.keycloak.storage.UserStorageProvider"}, headers=headers)

    if not any(c.get('name') == 'ldap-provider' for c in r.json()):
        ldap_data = {
            "name": "ldap-provider",
            "providerId": "ldap",
            "providerType": "org.keycloak.storage.UserStorageProvider",
            "parentId": REALM,
            "config": {
                "priority": ["0"],
                "fullSyncPeriod": ["-1"],
                "changedSyncPeriod": ["-1"],
                "cachePolicy": ["DEFAULT"],
                "batchSizeForSync": ["1000"],
                "editMode": ["READ_ONLY"],
                "syncRegistrations": ["false"],
                "vendor": ["other"],
                "usernameLDAPAttribute": ["uid"],
                "rdnLDAPAttribute": ["uid"],
                "uuidLDAPAttribute": ["entryUUID"],
                "userObjectClasses": ["inetOrgPerson, organizationalPerson"],
                "connectionUrl": ["ldap://ldap:389"],
                "usersDn": ["ou=People,dc=example,dc=com"],
                "authType": ["simple"],
                "bindDn": ["cn=admin,dc=example,dc=com"],
                "bindCredential": ["admin"],
                "searchScope": ["1"],
                "validatePasswordPolicy": ["false"],
                "trustEmail": ["false"],
                "useTruststoreSpi": ["ldapsOnly"],
                "connectionPooling": ["true"]
            }
        }
        res = requests.post(components_url, json=ldap_data, headers=headers)
        if res.status_code >= 200 and res.status_code < 300:
            print("LDAP Provider added.")
            # Add Mapper? (Task 4: "Add mapping of roles")
            # We need the ID of the component we just created.
            # Reread components
            r_new = requests.get(components_url, params={"parent": REALM, "type": "org.keycloak.storage.UserStorageProvider"}, headers=headers)
            ldap_comp = next((c for c in r_new.json() if c['name'] == 'ldap-provider'), None)
            if ldap_comp:
                ldap_id = ldap_comp['id']
                # Create role mapper
                # Endpoint: POST /admin/realms/{realm}/components
                # Mapper type: org.keycloak.storage.ldap.mappers.LDAPStorageMapper
                mapper_data = {
                    "name": "role-mapper",
                    "providerId": "role-ldap-mapper",
                    "providerType": "org.keycloak.storage.ldap.mappers.LDAPStorageMapper",
                    "parentId": ldap_id,
                    "config": {
                        "roles.dn": ["ou=Groups,dc=example,dc=com"],
                        "role.name.ldap.attribute": ["cn"],
                        "role.object.classes": ["groupOfNames"],
                        "membership.ldap.attribute": ["member"],
                        "membership.attribute.type": ["DN"],
                        "membership.user.ldap.attribute": ["uid"],
                        "mode": ["READ_ONLY"],
                        "user.roles.retrieve.strategy": ["LOAD_ROLES_BY_MEMBER_ATTRIBUTE"],
                        "use.realm.roles.mapping": ["true"]
                    }
                }
                res_map = requests.post(components_url, json=mapper_data, headers=headers)
                if res_map.status_code < 300:
                    print("LDAP Role Mapper added.")
                else:
                    print(f"Failed to add mapper: {res_map.text}")

        else:
             print(f"Failed to add LDAP: {res.text}")
    else:
        print("LDAP Provider already exists.")

    # 3. MFA (Task 5)
    print("Configuring MFA (OTP) as REQUIRED...")
    flows_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/authentication/flows/browser/executions"
    r = requests.get(flows_url, headers=headers)
    if r.status_code == 200:
        for exe in r.json():
            if exe.get("providerId") == "auth-otp-form":
                exe_id = exe["id"]
                print(f"Found OTP execution: {exe_id}")
                req_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/authentication/executions/{exe_id}/requirement"
                res = requests.put(req_url, json={"requirement": "REQUIRED"}, headers=headers)
                if res.status_code < 300:
                    print("MFA set to REQUIRED.")
                else:
                    print(f"Failed to set MFA: {res.text}")

    # 4. Yandex ID (Task 6)
    print("Adding Yandex ID...")
    idp_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/identity-provider/instances"
    r = requests.get(idp_url, headers=headers)
    if not any(i.get('alias') == 'yandex' for i in r.json()):
        yandex_data = {
            "alias": "yandex",
            "providerId": "yandex",
            "enabled": True,
            "config": {
                "clientId": "placeholder_client_id",
                "clientSecret": "placeholder_client_secret"
            }
        }
        res = requests.post(idp_url, json=yandex_data, headers=headers)
        if res.status_code < 300:
            print("Yandex IDP added.")
        else:
            print(f"Failed to add Yandex IDP: {res.text}")
    else:
        print("Yandex IDP already exists.")

if __name__ == "__main__":
    main()
