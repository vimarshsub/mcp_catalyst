## Design for SSE-Compatible MCP Server Endpoint for n8n Integration

**Date:** May 10, 2025

### 1. Introduction

This document outlines the design for modifying the existing Flask-based MCP server to add a Server-Sent Events (SSE) compatible endpoint. This is required for integration with n8n, as its "MCP Client Tool" node expects to connect to an MCP server via an SSE endpoint. The existing HTTP POST `/mcp` endpoint will remain functional for clients like Claude Desktop.

### 2. Requirements

-   The server must expose a new endpoint (e.g., `/mcp/sse`) that supports SSE.
-   This SSE endpoint must handle MCP requests (like `mcp/getServerCapabilities` and `mcp/executeTool`) initiated by n8n.
-   JSON-RPC requests (method, params, id) will be received via URL query parameters on a GET request to the SSE endpoint.
-   JSON-RPC responses (result or error) must be streamed back to n8n formatted as SSE events.
-   No additional authentication is required for this SSE endpoint beyond what the MCP server already handles for Catalyst Center API access.
-   The new SSE endpoint must coexist with the existing `/mcp` POST endpoint.

### 3. Proposed Architecture

#### 3.1. New Flask Endpoint

-   A new route will be added to the Flask application: `GET /mcp/sse`.
-   This endpoint will be responsible for handling incoming requests from n8n and streaming SSE responses.

#### 3.2. Request Handling

-   The `GET /mcp/sse` endpoint will expect JSON-RPC request components as URL query parameters:
    -   `jsonrpc`: The JSON-RPC version (e.g., "2.0").
    -   `method`: The MCP method to be invoked (e.g., "mcp/getServerCapabilities", "mcp/executeTool").
    -   `id`: The request identifier.
    -   `params`: (Optional) A URL-encoded JSON string representing the parameters for the MCP method. For `mcp/executeTool`, this would contain `toolId` and `inputs`.
-   The Flask route handler will parse these query parameters to reconstruct the JSON-RPC request.

#### 3.3. SSE Response Streaming

-   The Flask endpoint will return a `Response` object with `mimetype='text/event-stream'`.
-   A generator function will be used with `stream_with_context` to stream responses.
-   Each JSON-RPC response (either a result or an error object) will be formatted as an SSE event. A typical event structure will be:
    ```
    id: <request_id_from_n8n>
    event: mcpResponse
    data: <json_string_of_the_json_rpc_response_payload>
    
    ```
-   The connection will likely stream one primary response event and then potentially close, or it could be kept alive if further server-pushed updates are part of the MCP-over-SSE interaction model n8n expects (though this is less clear from the n8n docs and simple request-response is more likely for tool execution).

#### 3.4. MCP Method Processing Logic

-   The core logic for handling MCP methods (`mcp/getServerCapabilities`, `mcp/executeTool`) will be refactored or reused from the existing `/mcp` POST endpoint handler.
-   This includes:
    -   Defining server capabilities.
    -   Invoking the `CatalystClient` to interact with the Cisco Catalyst Center API.
    -   Constructing JSON-RPC success or error response objects.

#### 3.5. Error Handling

-   Errors originating from the Catalyst API, MCP method processing, or request parsing will be formulated as JSON-RPC error objects.
-   These error objects will be streamed back to n8n as SSE events, similar to how success responses are sent.
    Example error event data: `{"jsonrpc": "2.0", "error": {"code": <error_code>, "message": "<error_message>"}, "id": <request_id>}`

#### 3.6. Flask Implementation Details

-   The `app.py` file will be modified to include the new `/mcp/sse` route.
-   Libraries needed: `Flask`, `json`, `urllib.parse` (for URL decoding query parameters).
-   The `CatalystClient` remains unchanged.

### 4. Example Interaction Flow (Conceptual)

1.  **n8n initiates a request to get server capabilities:**
    n8n sends: `GET /mcp/sse?jsonrpc=2.0&method=mcp/getServerCapabilities&id=n8n_req_1`

2.  **MCP Server processes and streams response:**
    Server streams back:
    ```sse
    id: n8n_req_1
    event: mcpResponse
    data: {"jsonrpc": "2.0", "result": {"tools": [{"toolId": "catalyst_api_tool", ...}]}, "id": "n8n_req_1"}
    
    ```

3.  **n8n initiates a request to execute a tool:**
    n8n sends: `GET /mcp/sse?jsonrpc=2.0&method=mcp/executeTool&params=%7B%22toolId%22%3A%22catalyst_api_tool%22%2C%22inputs%22%3A%7B%22http_method%22%3A%22GET%22%2C%22endpoint_path%22%3A%22%2Fdna%2Fintent%2Fapi%2Fv1%2Fsite%22%7D%7D&id=n8n_req_2`
    (where `params` is the URL-encoded JSON string: `{"toolId":"catalyst_api_tool","inputs":{"http_method":"GET","endpoint_path":"/dna/intent/api/v1/site"}}`)

4.  **MCP Server processes, calls Catalyst API, and streams response:**
    Server streams back:
    ```sse
    id: n8n_req_2
    event: mcpResponse
    data: {"jsonrpc": "2.0", "result": {"outputs": {"status_code": 200, "response_body": [...]}}, "id": "n8n_req_2"}
    
    ```

### 5. Coexistence with Existing `/mcp` Endpoint

The new `/mcp/sse` GET endpoint will operate independently of the existing `/mcp` POST endpoint. This ensures that clients like Claude Desktop can continue to use the POST-based JSON-RPC mechanism.

### 6. Open Questions/Considerations (for implementation phase)

-   **SSE Connection Lifecycle:** Determine if the SSE connection should close after sending the response for a single request, or if n8n expects it to be long-lived for multiple messages. The design assumes a response-per-request model for now.
-   **Complexity of `params` in GET:** Very large `params` objects could lead to overly long URLs. This is a limitation of using GET for complex data, but seems to be implied by n8n's single "SSE Endpoint" configuration.

This design provides a foundation for implementing the SSE-compatible MCP endpoint. Further refinements may occur during the implementation phase.
