# /home/ubuntu/mcp_server_project/app.py
import os
import json
import urllib.parse
import time # Added for debugging delays
from flask import Flask, request, jsonify, Response, stream_with_context
from catalyst_client import CatalystClient, CatalystClientError
import uuid # For generating unique IDs
from mcp_mappings import RESOURCES, TOOLS, PROMPTS, get_resource_methods, get_tool_parameters, get_prompt_steps

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
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "capabilities": {
                    "tools": {
                        "supportedMethods": ["tools/list", "tools/call"]
                    },
                    "resources": {
                        "supportedMethods": ["resources/list", "resources/read"]
                    },
                    "prompts": {
                        "supportedMethods": ["prompts/list", "prompts/get"]
                    }
                },
                "serverInfo": {
                    "name": "catalyst-center-mcp-server",
                    "version": "1.0.0"
                }
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "id": tool_id,
                        "name": tool_info["name"],
                        "description": tool_info["description"],
                        "parameters": tool_info["parameters"]
                    }
                    for tool_id, tool_info in TOOLS.items()
                ]
            }
        }

    elif method == "tools/call":
        tool_id = params.get("toolId")
        inputs = params.get("inputs")

        if tool_id not in TOOLS:
            return {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Tool {tool_id} not found"}, "id": request_id}

        if not inputs or not isinstance(inputs, dict):
            return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "Invalid params: inputs missing or not an object"}, "id": request_id}

        if tool_id == "catalyst_api_tool":
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
                app.logger.error(f"Catalyst Client Error during tools/call: {e}")
                return {"jsonrpc": "2.0", "error": {"code": 1001, "message": "Catalyst API request failed", "data": str(e)}, "id": request_id}
            except Exception as e:
                app.logger.error(f"Unexpected error during tools/call: {e}", exc_info=True)
                return {"jsonrpc": "2.0", "error": {"code": -32000, "message": "Server error", "data": str(e)}, "id": request_id}
        
        elif tool_id == "deploy_template":
            template_id = inputs.get("templateId")
            device_ids = inputs.get("deviceIds")
            
            if not template_id or not device_ids:
                return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "Invalid params: templateId and deviceIds are required"}, "id": request_id}
            
            try:
                client = CatalystClient()
                # First verify template exists
                template = client.make_request("GET", f"/dna/intent/api/v1/template-programmer/template/{template_id}")
                if not template:
                    return {"jsonrpc": "2.0", "error": {"code": 1002, "message": f"Template {template_id} not found"}, "id": request_id}
                
                # Deploy template
                deploy_data = {
                    "templateId": template_id,
                    "targetInfo": [{"id": device_id, "type": "MANAGED_DEVICE_IP"} for device_id in device_ids]
                }
                deployment = client.make_request("POST", "/dna/intent/api/v1/template-programmer/template/deploy", data=deploy_data)
                return {"jsonrpc": "2.0", "result": {"outputs": deployment}, "id": request_id}
            except CatalystClientError as e:
                app.logger.error(f"Catalyst Client Error during template deployment: {e}")
                return {"jsonrpc": "2.0", "error": {"code": 1001, "message": "Template deployment failed", "data": str(e)}, "id": request_id}
        
        elif tool_id == "provision_device":
            device_info = inputs.get("deviceInfo")
            site_id = inputs.get("siteId")
            
            if not device_info or not site_id:
                return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "Invalid params: deviceInfo and siteId are required"}, "id": request_id}
            
            try:
                client = CatalystClient()
                # First verify site exists
                site = client.make_request("GET", f"/dna/intent/api/v1/site/{site_id}")
                if not site:
                    return {"jsonrpc": "2.0", "error": {"code": 1002, "message": f"Site {site_id} not found"}, "id": request_id}
                
                # Provision device
                provision_data = {
                    **device_info,
                    "siteId": site_id
                }
                device = client.make_request("POST", "/dna/intent/api/v1/network-device", data=provision_data)
                return {"jsonrpc": "2.0", "result": {"outputs": device}, "id": request_id}
            except CatalystClientError as e:
                app.logger.error(f"Catalyst Client Error during device provisioning: {e}")
                return {"jsonrpc": "2.0", "error": {"code": 1001, "message": "Device provisioning failed", "data": str(e)}, "id": request_id}

    elif method == "resources/list":
        # Return all available resources with a 'uri' field
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "resources": [
                    {
                        "id": resource_id,
                        "name": resource_info["name"],
                        "description": resource_info["description"],
                        "uri": f"/mcp/resource/{resource_id}",
                        "methods": {
                            method_name: {
                                "name": method_info["name"],
                                "description": method_info["description"]
                            }
                            for method_name, method_info in resource_info["methods"].items()
                        }
                    }
                    for resource_id, resource_info in RESOURCES.items()
                ]
            }
        }

    elif method == "resources/read":
        resource_name = params.get("resourceName")
        resource_id = params.get("resourceId")
        uri = params.get("uri")
        if uri and not resource_name:
            parts = uri.strip("/").split("/")
            if len(parts) == 3 and parts[0] == "mcp" and parts[1] == "resource":
                resource_name = parts[2]
        if not resource_name or resource_name not in RESOURCES:
            return {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Resource {resource_name} not found"}, "id": request_id}
        try:
            client = CatalystClient()
            resource = RESOURCES[resource_name]
            if resource_id:
                # Read a specific resource
                read_method = resource["methods"]["read"]
                endpoint = read_method["endpoint"].format(**{f"{resource_name[:-1]}Id": resource_id})
                response = client.make_request(method=read_method["http_method"], endpoint_path=endpoint)
                return {"jsonrpc": "2.0", "result": {"item": response}, "id": request_id}
            else:
                # Read all resources of this type
                list_method = resource["methods"]["list"]
                response = client.make_request(method=list_method["http_method"], endpoint_path=list_method["endpoint"])
                # Transform the response into the expected format
                contents = [
                    {
                        "uri": f"/mcp/resource/{resource_name}/{item['id']}",
                        "text": f"{resource_name.capitalize()} Name: {item['name']}, Hierarchy: {item.get('siteNameHierarchy', 'N/A')}"
                    }
                    for item in response["response"]
                ]
                return {"jsonrpc": "2.0", "result": {"contents": contents}, "id": request_id}
        except CatalystClientError as e:
            app.logger.error(f"Catalyst Client Error during resource read: {e}")
            return {"jsonrpc": "2.0", "error": {"code": 1001, "message": "Resource read failed", "data": str(e)}, "id": request_id}

    elif method == "prompts/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "prompts": [
                    {
                        "id": prompt_id,
                        "name": prompt_info["name"],
                        "description": prompt_info["description"]
                    }
                    for prompt_id, prompt_info in PROMPTS.items()
                ]
            }
        }

    elif method == "prompts/get":
        prompt_id = params.get("promptId")
        if not prompt_id or prompt_id not in PROMPTS:
            return {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Prompt {prompt_id} not found"}, "id": request_id}
        
        prompt = PROMPTS[prompt_id]
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "prompt": {
                    "id": prompt_id,
                    "name": prompt["name"],
                    "description": prompt["description"],
                    "steps": prompt["steps"]
                }
            }
        }

    else:
        return {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Method {method} not found"}, "id": request_id}

# --- NEW SSE Session Handshake Endpoint ---
@app.route("/mcp/sse_session", methods=["GET", "POST"])
def handle_sse_session_handshake():
    app.logger.info(f"Request received for /mcp/sse_session with method: {request.method}")
    
    if request.method == "POST":
        try:
            data = request.get_json()
            app.logger.info(f"Received POST data: {data}")
            
            # Extract session ID from the endpoint URL in the data
            if data and isinstance(data, dict) and "endpoint" in data:
                endpoint_url = data["endpoint"]
                session_id = endpoint_url.split("/")[-1]
                app.logger.info(f"Extracted session ID from endpoint URL: {session_id}")
                
                if session_id in active_sessions:
                    method = data.get("method")
                    params = data.get("params", {})
                    request_id = data.get("id")
                    
                    app.logger.info(f"Processing POST for session {session_id}: method={method}, id={request_id}")
                    
                    if method == "initialized":
                        app.logger.info(f"Received initialized notification for session {session_id}")
                        return jsonify({"jsonrpc": "2.0", "result": None, "id": request_id})
                    
                    response_payload = process_mcp_logic(method, params, request_id)
                    app.logger.info(f"Sending response for session {session_id}: {response_payload}")
                    
                    # Send response as SSE event
                    response = Response(
                        f"event: message\ndata: {json.dumps(response_payload)}\n\n",
                        mimetype="text/event-stream",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                            "X-Accel-Buffering": "no"
                        }
                    )
                    return response
                else:
                    app.logger.warning(f"Invalid session ID: {session_id}")
                    return jsonify({"jsonrpc": "2.0", "error": {"code": -32001, "message": "Invalid session ID"}, "id": None}), 401
            else:
                # Handle direct JSON-RPC requests without endpoint in data
                if data and isinstance(data, dict) and "jsonrpc" in data and "method" in data:
                    method = data.get("method")
                    params = data.get("params", {})
                    request_id = data.get("id")
                    
                    app.logger.info(f"Processing direct JSON-RPC request: method={method}, id={request_id}")
                    
                    if method == "initialized":
                        app.logger.info("Received initialized notification")
                        return jsonify({"jsonrpc": "2.0", "result": None, "id": request_id})
                    
                    response_payload = process_mcp_logic(method, params, request_id)
                    app.logger.info(f"Sending response: {response_payload}")
                    
                    # Send response as SSE event
                    response = Response(
                        f"event: message\ndata: {json.dumps(response_payload)}\n\n",
                        mimetype="text/event-stream",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                            "X-Accel-Buffering": "no"
                        }
                    )
                    return response
                else:
                    app.logger.warning(f"Invalid POST data format: {data}")
                    return jsonify({"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": None}), 400
                
        except Exception as e:
            app.logger.error(f"Error processing session RPC request: {str(e)}", exc_info=True)
            return jsonify({"jsonrpc": "2.0", "error": {"code": -32000, "message": f"Server error: {str(e)}"}, "id": None}), 500

    # Handle GET request for SSE connection
    session_id = str(uuid.uuid4())
    session_endpoint = f"/mcp/session/{session_id}"
    active_sessions[session_id] = {
        "created_at": time.time()
    }
    app.logger.info(f"New SSE session created: {session_id}")

    def generate_handshake_event():
        app.logger.info(f"Inside generate_handshake_event for session {session_id}")
        
        # Send the endpoint configuration event in the exact format required
        endpoint_event_data = {
            "endpoint": f"http://localhost:5001/mcp/session/{session_id}"
        }
        # Send the event with proper formatting
        yield f"event: endpoint\ndata: {json.dumps(endpoint_event_data)}\n\n"
        
        # Keep stream alive with periodic pings
        try:
            while True:
                app.logger.debug(f"SSE session {session_id}: sending keepalive ping")
                yield ": keepalive\n\n"
                time.sleep(15) # Send a comment every 15 seconds
        except GeneratorExit:
            app.logger.info(f"SSE client for session {session_id} disconnected.")
        finally:
            if session_id in active_sessions:
                del active_sessions[session_id]
                app.logger.info(f"SSE session {session_id} cleaned up from active_sessions.")

    response = Response(
        stream_with_context(generate_handshake_event()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
    return response

# --- Catch-all route for malformed URLs ---
@app.route("/mcp/<path:session_config>", methods=["POST"])
def handle_malformed_url(session_config):
    app.logger.info(f"Received malformed URL: /mcp/{session_config}")
    try:
        # Try to extract the session ID from the malformed URL
        session_data = json.loads(urllib.parse.unquote(session_config))
        if isinstance(session_data, dict) and "endpoint" in session_data:
            endpoint_url = session_data["endpoint"]
            session_id = endpoint_url.split("/")[-1]
            app.logger.info(f"Extracted session ID from malformed URL: {session_id}")
            
            # Forward the request to the correct endpoint
            return handle_sse_session_handshake()
    except:
        pass
    
    return jsonify({"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": None}), 400

# --- OLD/Existing Endpoints (kept for reference or potential backward compatibility) ---
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

