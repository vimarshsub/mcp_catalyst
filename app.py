# /home/ubuntu/mcp_server_project/app.py
import os
import json
import urllib.parse
import time # Added for debugging delays
from flask import Flask, request, jsonify, Response, stream_with_context
from catalyst_client import CatalystClient, CatalystClientError
import uuid # For generating unique IDs

app = Flask(__name__)

# In-memory store for active SSE sessions and their associated POST endpoints
active_sessions = {}

# --- Minimal SSE Test Endpoint ---
@app.route("/mcp/test_sse", methods=["GET"])
def handle_test_sse():
    app.logger.info("Request received for /mcp/test_sse")
    def generate_test_events():
        app.logger.info("Inside generate_test_events")
        yield "event: test\ndata: {\"message\": \"Hello from test SSE!\"}\n\n"
        app.logger.info("Yielded first test event")
        time.sleep(1) # Ensure client has time to receive
        yield "event: test\ndata: {\"message\": \"Still here!\"}\n\n"
        app.logger.info("Yielded second test event and finishing")
    return Response(stream_with_context(generate_test_events()), mimetype="text/event-stream")

# --- Helper function to process MCP requests (reused) ---
def process_mcp_logic(method, params, request_id):
    app.logger.info(f"Processing MCP Logic: method={method}, params={params}, id={request_id}")
    if method == "mcp/getServerCapabilities":
        capabilities = {
            "tools": [
                {
                    "toolId": "catalyst_api_tool",
                    "name": "CatalystCenterAPITool",
                    "description": "A tool to make API calls to a Cisco Catalyst Center instance. Input should be a JSON object specifying http_method, endpoint_path, and optionally request_params and request_body.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "http_method": {"type": "string", "description": "HTTP method (e.g., GET, POST, PUT, DELETE)"},
                            "endpoint_path": {"type": "string", "description": "API endpoint path (e.g., /dna/intent/api/v1/site)"},
                            "request_params": {"type": "object", "description": "(Optional) Dictionary of query parameters"},
                            "request_body": {"type": "object", "description": "(Optional) Dictionary for the request body (for POST, PUT)"}
                        },
                        "required": ["http_method", "endpoint_path"]
                    },
                    "outputSchema": {
                        "type": "object",
                        "properties": {
                            "status_code": {"type": "integer"},
                            "response_body": {"type": ["object", "array", "string", "null"]}
                        }
                    }
                }
            ]
        }
        return {"jsonrpc": "2.0", "result": capabilities, "id": request_id}

    elif method == "mcp/executeTool":
        tool_id = params.get("toolId")
        inputs = params.get("inputs")

        if tool_id == "catalyst_api_tool":
            if not inputs or not isinstance(inputs, dict):
                return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "Invalid params: inputs missing or not an object"}, "id": request_id}

            http_method = inputs.get("http_method")
            endpoint_path = inputs.get("endpoint_path")
            request_params = inputs.get("request_params")
            request_body = inputs.get("request_body")

            if not http_method or not endpoint_path:
                return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "Invalid params: http_method and endpoint_path are required in inputs"}, "id": request_id}
            
            try:
                client = CatalystClient()
                app.logger.info(f"Executing Catalyst API Tool: {http_method} {endpoint_path}")
                api_response_data = client.make_request(
                    method=http_method.upper(),
                    endpoint_path=endpoint_path,
                    params=request_params,
                    data=request_body
                )
                tool_result = {
                    "status_code": client.last_response_status_code,
                    "response_body": api_response_data
                }
                return {"jsonrpc": "2.0", "result": {"outputs": tool_result}, "id": request_id}
            except CatalystClientError as e:
                app.logger.error(f"Catalyst Client Error during mcp/executeTool: {e}")
                return {"jsonrpc": "2.0", "error": {"code": 1001, "message": "Catalyst API request failed", "data": str(e)}, "id": request_id}
            except Exception as e:
                app.logger.error(f"Unexpected error during mcp/executeTool: {e}", exc_info=True)
                return {"jsonrpc": "2.0", "error": {"code": -32000, "message": "Server error", "data": str(e)}, "id": request_id}
        else:
            return {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found: Unknown toolId"}, "id": request_id}
    else:
        return {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": request_id}

# --- NEW SSE Session Handshake Endpoint ---
@app.route("/mcp/sse_session", methods=["GET"])
def handle_sse_session_handshake():
    app.logger.info("Request received for /mcp/sse_session")
    session_id = str(uuid.uuid4())
    post_endpoint_path = "/mcp/session_rpc"
    active_sessions[session_id] = {"post_endpoint": post_endpoint_path} # Store session
    app.logger.info(f"New SSE session created: {session_id}, POST endpoint: {post_endpoint_path}")

    def generate_handshake_event():
        app.logger.info(f"Inside generate_handshake_event for session {session_id}")
        endpoint_event_data = {
            "sessionId": session_id,
            "postEndpoint": post_endpoint_path 
        }
        sse_event = f"event: endpoint\ndata: {json.dumps(endpoint_event_data)}\n\n"
        app.logger.info(f"Streaming SSE handshake event for session {session_id}: {sse_event.strip()}")
        time.sleep(0.1) # Small delay to help ensure log flush before yield
        yield sse_event
        app.logger.info(f"Finished yielding handshake event for session {session_id}")
        
        # Keep stream alive with periodic pings - uncomment and adapt if needed for long-lived client connections
        # try:
        #     while True:
        #         app.logger.debug(f"SSE session {session_id}: sending keepalive ping")
        #         yield ": keepalive\n\n"
        #         time.sleep(15) # Send a comment every 15 seconds
        # except GeneratorExit:
        #     app.logger.info(f"SSE client for session {session_id} disconnected.")
        # finally:
        #     if session_id in active_sessions:
        #         del active_sessions[session_id]
        #         app.logger.info(f"SSE session {session_id} cleaned up from active_sessions.")

    return Response(stream_with_context(generate_handshake_event()), mimetype="text/event-stream")

# --- NEW POST Endpoint for Session-Based JSON-RPC ---
@app.route("/mcp/session_rpc", methods=["POST"])
def handle_session_rpc_post():
    session_id = request.headers.get("X-Session-ID")
    app.logger.info(f"Request received for /mcp/session_rpc with X-Session-ID: {session_id}")
    if not session_id or session_id not in active_sessions:
        app.logger.warning(f"Invalid or missing X-Session-ID: {session_id}. Active sessions: {list(active_sessions.keys())}")
        return jsonify({"jsonrpc": "2.0", "error": {"code": -32001, "message": "Invalid or missing session ID"}, "id": None}), 401

    data = request.get_json()
    if not data or "jsonrpc" not in data or "method" not in data:
        app.logger.warning(f"Invalid JSON-RPC payload for session {session_id}: {data}")
        return jsonify({"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": data.get("id") if data else None}), 400

    method = data.get("method")
    params = data.get("params", {})
    request_id = data.get("id")
    
    app.logger.info(f"Processing POST for session {session_id}: method={method}, id={request_id}")
    response_payload = process_mcp_logic(method, params, request_id)
    return jsonify(response_payload)


# --- Old/Existing Endpoints (kept for reference or potential backward compatibility) ---
@app.route("/")
def hello_world():
    return "Hello, MCP Server Backend is running! (Now with MCP capabilities including NEW SSE session model)"

@app.route("/api/catalyst/request", methods=["POST"])
def handle_catalyst_request():
    try:
        req_data = request.get_json()
        if not req_data:
            return jsonify({"error": "Invalid JSON payload"}), 400
        api_method = req_data.get("method")
        endpoint_path = req_data.get("endpoint_path")
        api_params = req_data.get("params")
        api_body = req_data.get("data")
        if not api_method or not endpoint_path:
            return jsonify({"error": "Missing required fields: method and endpoint_path"}), 400
        client = CatalystClient()
        response_data = client.make_request(method=api_method, endpoint_path=endpoint_path, params=api_params, data=api_body)
        if response_data is None and client.last_response_status_code == 204:
            return jsonify({"message": "Operation successful, no content returned"}), 204
        return jsonify(response_data), 200
    except CatalystClientError as e: 
        app.logger.error(f"Catalyst Client Error: {e}")
        return jsonify({"error": "Catalyst API request failed", "details": str(e)}), 502
    except ValueError as e:
        app.logger.error(f"Value Error: {e}")
        return jsonify({"error": "Invalid request parameter", "details": str(e)}), 400
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred", "details": str(e)}), 500

@app.route("/api/catalyst/sites", methods=["GET"])
def get_sites():
    try:
        client = CatalystClient()
        sites_data = client.make_request("GET", "/dna/intent/api/v1/site")
        return jsonify(sites_data), 200
    except CatalystClientError as e: 
        app.logger.error(f"Catalyst Client Error fetching sites: {e}")
        return jsonify({"error": "Failed to fetch sites from Catalyst", "details": str(e)}), 502
    except Exception as e:
        app.logger.error(f"Unexpected error fetching sites: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred while fetching sites", "details": str(e)}), 500

@app.route("/mcp", methods=["POST"])
# Original MCP POST endpoint
def handle_mcp_post_request():
    data = request.get_json()
    if not data or "jsonrpc" not in data or "method" not in data:
        return jsonify({"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": data.get("id") if data else None}), 400
    method = data.get("method")
    params = data.get("params", {})
    request_id = data.get("id")
    response_payload = process_mcp_logic(method, params, request_id)
    return jsonify(response_payload)

@app.route("/mcp/sse") 
# Original MCP SSE endpoint (GET with params in query)
def handle_mcp_sse_request():
    jsonrpc_version = request.args.get("jsonrpc")
    method = request.args.get("method")
    request_id_str = request.args.get("id")
    params_str = request.args.get("params")
    app.logger.info(f"OLD MCP SSE Request Received: method={method}, params_str={params_str}, id={request_id_str}")
    if not jsonrpc_version or not method or request_id_str is None: 
        return jsonify({"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request: Missing jsonrpc, method, or id in query parameters"}, "id": request_id_str}), 400
    params = {}
    if params_str:
        try:
            params = json.loads(urllib.parse.unquote(params_str))
        except json.JSONDecodeError:
            return jsonify({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error: Invalid JSON in params query parameter"}, "id": request_id_str}), 400
    def generate_sse_events():
        response_payload = process_mcp_logic(method, params, request_id_str)
        sse_event_data = json.dumps(response_payload)
        sse_formatted_event = f"id: {request_id_str}\nevent: mcpResponse\ndata: {sse_event_data}\n\n"
        app.logger.info(f"Streaming OLD SSE event: {sse_formatted_event}")
        yield sse_formatted_event
    return Response(stream_with_context(generate_sse_events()), mimetype="text/event-stream")

if __name__ == "__main__":
    print("Starting Flask development server...")
    print(f"CATALYST_BASE_URL: {os.getenv('CATALYST_BASE_URL')}")
    print(f"CATALYST_USERNAME: {os.getenv('CATALYST_USERNAME')}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5001)), debug=True)

