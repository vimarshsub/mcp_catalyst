# MCP Server for Cisco Catalyst Center API

This project provides a server that acts as a bridge between MCP-compliant clients (like Claude Desktop or n8n) and a Cisco Catalyst Center API. It allows users to interact with the Catalyst Center using natural language queries through AI agents or automation workflows.

## Features

-   Exposes Catalyst Center API functionalities as a tool for MCP clients.
-   Handles authentication with the Catalyst Center.
-   Provides two MCP endpoints:
    -   A JSON-RPC POST endpoint (`/mcp`) for clients like Claude Desktop.
    -   A Server-Sent Events (SSE) GET endpoint (`/mcp/sse`) for clients like n8n.

## Setup and Usage

### Prerequisites

-   Python 3.11 or higher.
-   Access to a Cisco Catalyst Center instance with API credentials (username, password, and base URL).

### Backend Server Setup

1.  **Clone the repository (if applicable) or ensure all files are in place.**
2.  **Navigate to the backend directory:**
    ```bash
    cd /home/ubuntu/mcp_server_project/backend
    ```
3.  **Set up the Python virtual environment (if not already done during development):**
    ```bash
    python3.11 -m venv venv
    source venv/bin/activate
    pip3 install -r requirements.txt
    ```
4.  **Set Environment Variables:**
    The server requires the following environment variables to connect to your Catalyst Center:
    -   `CATALYST_BASE_URL`: The base URL of your Catalyst Center API (e.g., `https://your-catalyst-center-ip`).
    -   `CATALYST_USERNAME`: Your Catalyst Center username.
    -   `CATALYST_PASSWORD`: Your Catalyst Center password.

    You can set these in your shell before running the server:
    ```bash
    export CATALYST_BASE_URL="https://your-catalyst-center-ip"
    export CATALYST_USERNAME="your_username"
    export CATALYST_PASSWORD="your_password"
    ```
5.  **Run the Server:**
    Use the provided shell script to start the server:
    ```bash
    chmod +x start_server.sh
    ./start_server.sh
    ```
    The server will start on `http://0.0.0.0:5000` by default.

### Connecting MCP Clients

#### 1. For Claude Desktop App (or similar POST-based clients)

-   **MCP Server URL:** `http://<your-server-ip>:5000/mcp`
-   **Configuration:**
    -   Open your Claude Desktop App.
    -   Navigate to settings/integrations to add custom tools or MCP servers.
    -   Add a new MCP server using the URL above.
    -   Claude should discover the `CatalystCenterAPITool`.
-   **Tool Input Format (JSON in POST body):**
    ```json
    {
      "jsonrpc": "2.0",
      "method": "mcp/executeTool",
      "params": {
        "toolId": "catalyst_api_tool",
        "inputs": {
          "http_method": "GET",
          "endpoint_path": "/dna/intent/api/v1/site",
          "request_params": { "siteId": "some-site-id" }, // Optional
          "request_body": {} // Optional, for POST/PUT
        }
      },
      "id": "claude_request_123"
    }
    ```

#### 2. For n8n (or similar SSE-based clients)

-   **MCP Server SSE Endpoint URL:** `http://<your-server-ip>:5000/mcp/sse`
-   **n8n Configuration (MCP Client Tool node):**
    -   In your n8n workflow, add the "MCP Client Tool" node.
    -   In the node parameters, set the "SSE Endpoint" to the URL above.
    -   Authentication: Select "None" (as per current server setup).
    -   Tools to Include: Configure as needed (e.g., "All" to expose the `CatalystCenterAPITool`).
-   **Interaction (n8n handles this internally based on the MCP spec over SSE):**
    n8n will send GET requests to the SSE endpoint with JSON-RPC details as query parameters. For example, to get capabilities:
    `GET http://<server-ip>:5000/mcp/sse?jsonrpc=2.0&method=mcp/getServerCapabilities&id=<n8n_request_id>`

    To execute a tool:
    `GET http://<server-ip>:5000/mcp/sse?jsonrpc=2.0&method=mcp/executeTool&id=<n8n_request_id>&params=<URL_ENCODED_JSON_PARAMS>`
    Where `<URL_ENCODED_JSON_PARAMS>` would be the URL-encoded version of:
    `{"toolId":"catalyst_api_tool","inputs":{"http_method":"GET","endpoint_path":"/dna/intent/api/v1/network-device"}}`

    The server will stream back JSON-RPC responses formatted as SSE events.

### Using the `CatalystCenterAPITool` (General Input Structure)

The `CatalystCenterAPITool` (whether called via POST or SSE) expects the `inputs` to be a JSON object with:

```json
{
  "http_method": "GET", // e.g., GET, POST, PUT, DELETE
  "endpoint_path": "/dna/intent/api/v1/site", // Catalyst API path
  "request_params": { "siteId": "some-site-id" }, // Optional: for query parameters
  "request_body": {} // Optional: for request body in POST/PUT
}
```

## Development Notes

-   The main application logic is in `app.py`.
-   Catalyst Center API interaction is handled by `catalyst_client.py`.
-   Ensure `requirements.txt` is up-to-date with all dependencies.

## Troubleshooting

-   Check the server logs (`/home/ubuntu/mcp_server_project/backend/server.log`) for any errors.
-   Ensure the Catalyst Center credentials and base URL are correctly set as environment variables.
-   Verify network connectivity between the MCP server and the Catalyst Center instance.
-   Confirm that the Catalyst Center API endpoints you are trying to access are correct and that the provided credentials have the necessary permissions.


