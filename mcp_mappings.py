"""
MCP (Model Context Protocol) mappings for Catalyst Center APIs.
This file defines the resources, tools, and prompts available through the MCP interface.
"""

# Resources represent data that can be read or listed
RESOURCES = {
    "sites": {
        "name": "sites",
        "description": "Network sites in Catalyst Center",
        "methods": {
            "list": {
                "name": "resources/list",
                "description": "List all network sites",
                "endpoint": "/dna/intent/api/v1/site",
                "http_method": "GET"
            },
            "read": {
                "name": "resources/read",
                "description": "Get details of a specific site",
                "endpoint": "/dna/intent/api/v1/site/{siteId}",
                "http_method": "GET"
            }
        }
    },
    "devices": {
        "name": "devices",
        "description": "Network devices in Catalyst Center",
        "methods": {
            "list": {
                "name": "resources/list",
                "description": "List all network devices",
                "endpoint": "/dna/intent/api/v1/network-device",
                "http_method": "GET"
            },
            "read": {
                "name": "resources/read",
                "description": "Get details of a specific device",
                "endpoint": "/dna/intent/api/v1/network-device/{deviceId}",
                "http_method": "GET"
            }
        }
    },
    "templates": {
        "name": "templates",
        "description": "Configuration templates in Catalyst Center",
        "methods": {
            "list": {
                "name": "resources/list",
                "description": "List all configuration templates",
                "endpoint": "/dna/intent/api/v1/template-programmer/template",
                "http_method": "GET"
            },
            "read": {
                "name": "resources/read",
                "description": "Get details of a specific template",
                "endpoint": "/dna/intent/api/v1/template-programmer/template/{templateId}",
                "http_method": "GET"
            }
        }
    }
}

# Tools represent actions that can be performed
TOOLS = {
    "catalyst_api_tool": {
        "name": "catalyst_api_tool",
        "description": "Make requests to Catalyst Center API",
        "parameters": {
            "http_method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "DELETE"],
                "description": "HTTP method for the API request"
            },
            "endpoint_path": {
                "type": "string",
                "description": "API endpoint path"
            },
            "request_params": {
                "type": "object",
                "description": "Query parameters for the request"
            },
            "request_body": {
                "type": "object",
                "description": "Request body for POST/PUT requests"
            }
        }
    },
    "deploy_template": {
        "name": "deploy_template",
        "description": "Deploy a configuration template to devices",
        "parameters": {
            "templateId": {
                "type": "string",
                "description": "ID of the template to deploy"
            },
            "deviceIds": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of device IDs to deploy the template to"
            }
        }
    },
    "provision_device": {
        "name": "provision_device",
        "description": "Provision a new device in the network",
        "parameters": {
            "deviceInfo": {
                "type": "object",
                "description": "Device information for provisioning"
            },
            "siteId": {
                "type": "string",
                "description": "ID of the site to provision the device in"
            }
        }
    }
}

# Prompts represent predefined interactions or workflows
PROMPTS = {
    "device_onboarding": {
        "name": "device_onboarding",
        "description": "Guide through the process of onboarding a new device",
        "steps": [
            "List available sites",
            "Select a site for the device",
            "Enter device details",
            "Provision the device",
            "Verify device status"
        ]
    },
    "template_deployment": {
        "name": "template_deployment",
        "description": "Guide through deploying a configuration template",
        "steps": [
            "List available templates",
            "Select a template",
            "List target devices",
            "Select devices for deployment",
            "Deploy template",
            "Verify deployment status"
        ]
    },
    "site_management": {
        "name": "site_management",
        "description": "Guide through managing network sites",
        "steps": [
            "List all sites",
            "View site details",
            "Add new site",
            "Modify site configuration",
            "Delete site"
        ]
    }
}

def get_resource_methods(resource_name):
    """Get available methods for a resource."""
    if resource_name in RESOURCES:
        return RESOURCES[resource_name]["methods"]
    return None

def get_tool_parameters(tool_name):
    """Get parameters for a tool."""
    if tool_name in TOOLS:
        return TOOLS[tool_name]["parameters"]
    return None

def get_prompt_steps(prompt_name):
    """Get steps for a prompt."""
    if prompt_name in PROMPTS:
        return PROMPTS[prompt_name]["steps"]
    return None 