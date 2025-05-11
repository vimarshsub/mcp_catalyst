# /home/ubuntu/mcp_server_project/backend/catalyst_client.py
import requests
import json
import os

# Custom exception for Catalyst Client errors
class CatalystClientError(Exception):
    pass

# Hardcoded credentials for Catalyst Center
CATALYST_BASE_URL = "https://128.107.255.230"
CATALYST_USERNAME = "netadmin1"
CATALYST_PASSWORD = "LABC1sco123"

class CatalystClient:
    def __init__(self):
        self.base_url = CATALYST_BASE_URL
        self.username = CATALYST_USERNAME
        self.password = CATALYST_PASSWORD
        self.token = None
        self.last_response_status_code = None # To store the status code for 204 checks
        self._authenticate()

    def _authenticate(self):
        """Authenticates with the Catalyst Center and stores the token."""
        auth_url = f"{self.base_url}/dna/system/api/v1/auth/token"
        try:
            print(f"Attempting authentication to: {auth_url}")
            response = requests.post(auth_url, auth=(self.username, self.password), verify=False) 
            response.raise_for_status()
            self.token = response.json().get("Token")
            if not self.token:
                print("Authentication failed: Token not received.")
                raise CatalystClientError("Authentication failed: Token not received.")
            print("Successfully authenticated with Catalyst Center.")
        except requests.exceptions.RequestException as e:
            print(f"Error during authentication: {e}")
            raise CatalystClientError(f"Error during authentication: {e}")

    def _get_headers(self):
        if not self.token:
            print("Token is missing, attempting to re-authenticate...")
            self._authenticate()
        return {
            "X-Auth-Token": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def make_request(self, method, endpoint_path, params=None, data=None):
        """Makes a generic request to the Catalyst Center API."""
        if not endpoint_path.startswith("/"):
            endpoint_path = "/" + endpoint_path
        
        url = f"{self.base_url}{endpoint_path}"
        headers = self._get_headers()
        self.last_response_status_code = None

        print(f"Making {method.upper()} request to {url} with params={params}, data={data}")

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, verify=False)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, params=params, json=data, verify=False)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, params=params, json=data, verify=False)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, params=params, verify=False)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            self.last_response_status_code = response.status_code
            print(f"Response status code: {response.status_code}")
            response.raise_for_status()
            
            if response.status_code == 204:
                print("Received 204 No Content.")
                return None 
            
            if not response.content:
                print("Response content is empty.")
                return None
                
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_details = e.response.text
            try:
                error_json = e.response.json()
                if isinstance(error_json, dict):
                    error_details = error_json.get("error", error_json.get("message", error_json))
            except json.JSONDecodeError:
                pass 
            print(f"HTTP error occurred: {e.response.status_code} - {e.response.reason}. Details: {error_details}")
            raise CatalystClientError(f"Catalyst API request failed: {e.response.status_code} - {error_details}") from e
        except requests.exceptions.RequestException as e:
            print(f"Request exception occurred: {e}")
            raise CatalystClientError(f"Catalyst API request failed: {e}") from e

if __name__ == "__main__":
    print("Attempting to create CatalystClient for direct testing...")
    print(f"Using base URL: {CATALYST_BASE_URL}")
    if CATALYST_BASE_URL == "https://your-catalyst-center-ip-or-fqdn" or CATALYST_USERNAME == "your_username":
        print("Please ensure CATALYST_BASE_URL, CATALYST_USERNAME, and CATALYST_PASSWORD are correctly set for direct testing.")
    else:
        try:
            client = CatalystClient()
            print("Client initialized. Attempting to get sites...")
            sites = client.make_request("GET", "/dna/intent/api/v1/site")
            if sites:
                print("Successfully fetched sites:")
                print(json.dumps(sites, indent=2))
            elif client.last_response_status_code == 204:
                print("Successfully called /dna/intent/api/v1/site, but no content was returned (204).")
            else:
                print("No sites data returned or an issue occurred.")
        except CatalystClientError as e:
            print(f"Could not connect or request Catalyst Center: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during direct testing: {e}")

