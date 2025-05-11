import json
import sys

# Read the initialize request
request_str = sys.stdin.readline()
request = json.loads(request_str)

# Prepare a minimal valid response
response = {
    "jsonrpc": "2.0",
    "id": request["id"],
    "result": {
        "protocolVersion": request["params"]["protocolVersion"],
        "capabilities": {
            "tools": {"supportedMethods": ["tools/list", "tools/call"]}
        },
        "serverInfo": {
            "name": "test-server",
            "version": "1.0.0"
        }
    }
}

# Send the response
print(json.dumps(response), flush=True)

# Wait for the initialized notification
while True:
    line = sys.stdin.readline()
    if not line:
        break
    message = json.loads(line)
    print(f"Received: {json.dumps(message)}", file=sys.stderr, flush=True)
    if message.get("method") == "initialized":
        print("Initialization complete!", file=sys.stderr, flush=True)
        break 