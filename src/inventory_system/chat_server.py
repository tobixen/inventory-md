#!/usr/bin/env python3
"""
FastAPI server for inventory chatbot with Claude integration.

Provides conversational interface for querying inventory.
"""
import os
import json
from pathlib import Path
from typing import Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic


# Global inventory data
inventory_data: Optional[dict] = None
inventory_path: Optional[Path] = None
aliases: Optional[dict] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load inventory and aliases on startup."""
    global inventory_data, inventory_path, aliases

    # Look for inventory.json in current directory
    inventory_path = Path.cwd() / "inventory.json"
    if not inventory_path.exists():
        print(f"⚠️  Warning: inventory.json not found at {inventory_path}")
        print("   Server will start but chatbot won't work until inventory.json is available")
    else:
        with open(inventory_path, 'r', encoding='utf-8') as f:
            inventory_data = json.load(f)
        print(f"✅ Loaded inventory: {len(inventory_data.get('containers', []))} containers")

    # Load aliases
    aliases_path = Path.cwd() / "aliases.json"
    if aliases_path.exists():
        with open(aliases_path, 'r', encoding='utf-8') as f:
            aliases = json.load(f)
        print(f"✅ Loaded {len(aliases)} search aliases")
    else:
        print(f"⚠️  aliases.json not found, search aliases disabled")
        aliases = {}

    yield

    # Cleanup
    inventory_data = None


app = FastAPI(title="Inventory Chatbot Server", lifespan=lifespan)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    """Chat message from user."""
    message: str
    conversation_id: Optional[str] = None
    model: str = "claude-3-haiku-20240307"  # Default to cheapest model


class ChatResponse(BaseModel):
    """Chat response from Claude."""
    response: str
    conversation_id: str


# Tool definitions for Claude
INVENTORY_TOOLS = [
    {
        "name": "search_inventory",
        "description": "Search the inventory for items, containers, or content matching a query. Returns relevant containers and items.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query - can be item name, container ID, tag, or description text"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_container",
        "description": "Get detailed information about a specific container by its ID",
        "input_schema": {
            "type": "object",
            "properties": {
                "container_id": {
                    "type": "string",
                    "description": "The container ID (e.g., 'A23', 'H11', 'Box5')"
                }
            },
            "required": ["container_id"]
        }
    },
    {
        "name": "list_containers",
        "description": "List all containers, optionally filtered by location/parent, tags, or prefix",
        "input_schema": {
            "type": "object",
            "properties": {
                "parent": {
                    "type": "string",
                    "description": "Filter by parent location (e.g., 'Garasje', 'Loft')"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by tags (e.g., ['winter', 'sport'])"
                },
                "prefix": {
                    "type": "string",
                    "description": "Filter by container ID prefix (e.g., 'A', 'H', 'C')"
                }
            }
        }
    },
    {
        "name": "add_item",
        "description": "Add a new item to a specific container. This modifies the inventory permanently.",
        "input_schema": {
            "type": "object",
            "properties": {
                "container_id": {
                    "type": "string",
                    "description": "The container ID to add the item to (e.g., 'A23', 'H11')"
                },
                "item_description": {
                    "type": "string",
                    "description": "Description of the item to add"
                },
                "tags": {
                    "type": "string",
                    "description": "Optional comma-separated tags (e.g., 'elektronikk,hjem')"
                }
            },
            "required": ["container_id", "item_description"]
        }
    },
    {
        "name": "remove_item",
        "description": "Remove an item from a container. This modifies the inventory permanently.",
        "input_schema": {
            "type": "object",
            "properties": {
                "container_id": {
                    "type": "string",
                    "description": "The container ID to remove the item from"
                },
                "item_description": {
                    "type": "string",
                    "description": "Description of the item to remove (or part of it)"
                }
            },
            "required": ["container_id", "item_description"]
        }
    }
]


def expand_query_with_aliases(query: str) -> list[str]:
    """Expand query with aliases. Returns list of search terms including query and all aliases."""
    if not aliases:
        return [query]

    query_lower = query.lower()
    search_terms = [query_lower]

    # Check if query matches any alias key
    if query_lower in aliases:
        search_terms.extend([a.lower() for a in aliases[query_lower]])

    return list(set(search_terms))  # Remove duplicates


def search_inventory(query: str) -> dict:
    """Search inventory for matching containers and items."""
    if not inventory_data:
        return {"error": "Inventory not loaded"}

    # Expand query with aliases
    search_terms = expand_query_with_aliases(query)

    results = {
        "matching_containers": [],
        "matching_items": []
    }

    for container in inventory_data.get('containers', []):
        container_match = False

        # Check container ID, heading, description with all search terms
        for term in search_terms:
            if (term in container.get('id', '').lower() or
                term in container.get('heading', '').lower() or
                term in container.get('description', '').lower()):
                container_match = True
                break

        # Check tags
        if not container_match and container.get('metadata', {}).get('tags'):
            for tag in container['metadata']['tags']:
                for term in search_terms:
                    if term in tag.lower():
                        container_match = True
                        break
                if container_match:
                    break

        # Check items
        matching_items_in_container = []
        for item in container.get('items', []):
            item_text = item.get('name', '') or item.get('raw_text', '')
            for term in search_terms:
                if term in item_text.lower():
                    matching_items_in_container.append(item_text)
                    container_match = True
                    break  # Don't add same item multiple times

        if container_match:
            results['matching_containers'].append({
                'id': container.get('id'),
                'heading': container.get('heading'),
                'parent': container.get('parent'),
                'description': container.get('description'),
                'tags': container.get('metadata', {}).get('tags', []),
                'item_count': len(container.get('items', [])),
                'image_count': len(container.get('images', [])),
                'matching_items': matching_items_in_container[:5]  # Limit to 5
            })

    return results


def get_container(container_id: str) -> dict:
    """Get detailed information about a container."""
    if not inventory_data:
        return {"error": "Inventory not loaded"}

    for container in inventory_data.get('containers', []):
        if container.get('id', '').lower() == container_id.lower():
            # Return full container info
            return {
                'id': container.get('id'),
                'heading': container.get('heading'),
                'parent': container.get('parent'),
                'description': container.get('description'),
                'metadata': container.get('metadata', {}),
                'items': [item.get('name') or item.get('raw_text') for item in container.get('items', [])],
                'image_count': len(container.get('images', [])),
                'images': container.get('images', [])[:3]  # First 3 images
            }

    return {"error": f"Container '{container_id}' not found"}


def list_containers(parent: Optional[str] = None, tags: Optional[list] = None, prefix: Optional[str] = None) -> dict:
    """List containers with optional filters."""
    if not inventory_data:
        return {"error": "Inventory not loaded"}

    containers = []

    for container in inventory_data.get('containers', []):
        # Apply filters
        if parent and container.get('parent', '').lower() != parent.lower():
            continue

        if prefix and not container.get('id', '').startswith(prefix):
            continue

        if tags:
            container_tags = container.get('metadata', {}).get('tags', [])
            if not any(tag.lower() in [t.lower() for t in container_tags] for tag in tags):
                continue

        containers.append({
            'id': container.get('id'),
            'heading': container.get('heading'),
            'parent': container.get('parent'),
            'tags': container.get('metadata', {}).get('tags', []),
            'item_count': len(container.get('items', [])),
            'image_count': len(container.get('images', []))
        })

    return {
        'count': len(containers),
        'containers': containers[:50]  # Limit to 50
    }


def reload_inventory() -> bool:
    """Reload inventory.json after markdown changes."""
    global inventory_data

    if not inventory_path or not inventory_path.exists():
        return False

    try:
        with open(inventory_path, 'r', encoding='utf-8') as f:
            inventory_data = json.load(f)
        return True
    except Exception as e:
        print(f"❌ Error reloading inventory: {e}")
        return False


def add_item_to_container(container_id: str, item_description: str, tags: Optional[str] = None) -> dict:
    """Add an item to a container by modifying the markdown file."""
    if not inventory_path:
        return {"error": "Inventory path not set"}

    markdown_path = inventory_path.parent / "inventory.md"
    if not markdown_path.exists():
        return {"error": "inventory.md not found"}

    try:
        # Read markdown file
        with open(markdown_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Find the container
        container_line_idx = None
        for i, line in enumerate(lines):
            if line.startswith('## ') and f'ID:{container_id}' in line:
                container_line_idx = i
                break

        if container_line_idx is None:
            return {"error": f"Container ID:{container_id} not found in markdown"}

        # Find where to insert the item (after the header, before next ## or end)
        insert_idx = container_line_idx + 1

        # Skip blank lines and description
        while insert_idx < len(lines) and (lines[insert_idx].strip() == '' or
                                           not lines[insert_idx].startswith(('*', '#'))):
            insert_idx += 1

        # Create the item line
        if tags:
            item_line = f"* tag:{tags} {item_description}\n"
        else:
            item_line = f"* {item_description}\n"

        # Insert the item
        lines.insert(insert_idx, item_line)

        # Write back to file
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        # Regenerate JSON
        from inventory_system import parser
        parser.parse_inventory(markdown_path, output_path=inventory_path)

        # Reload inventory data
        reload_inventory()

        return {
            "success": True,
            "message": f"Added '{item_description}' to container {container_id}",
            "container_id": container_id,
            "item": item_description
        }

    except Exception as e:
        return {"error": f"Failed to add item: {str(e)}"}


def remove_item_from_container(container_id: str, item_description: str) -> dict:
    """Remove an item from a container by modifying the markdown file."""
    if not inventory_path:
        return {"error": "Inventory path not set"}

    markdown_path = inventory_path.parent / "inventory.md"
    if not markdown_path.exists():
        return {"error": "inventory.md not found"}

    try:
        # Read markdown file
        with open(markdown_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Find the container section
        container_line_idx = None
        for i, line in enumerate(lines):
            if line.startswith('## ') and f'ID:{container_id}' in line:
                container_line_idx = i
                break

        if container_line_idx is None:
            return {"error": f"Container ID:{container_id} not found"}

        # Find and remove the item
        item_removed = False
        i = container_line_idx + 1
        while i < len(lines) and not lines[i].startswith('## '):
            if lines[i].startswith('* ') and item_description.lower() in lines[i].lower():
                del lines[i]
                item_removed = True
                break
            i += 1

        if not item_removed:
            return {"error": f"Item '{item_description}' not found in container {container_id}"}

        # Write back
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        # Regenerate JSON
        from inventory_system import parser
        parser.parse_inventory(markdown_path, output_path=inventory_path)

        # Reload
        reload_inventory()

        return {
            "success": True,
            "message": f"Removed '{item_description}' from container {container_id}",
            "container_id": container_id
        }

    except Exception as e:
        return {"error": f"Failed to remove item: {str(e)}"}


def execute_tool(tool_name: str, tool_input: dict) -> dict:
    """Execute a tool and return results."""
    if tool_name == "search_inventory":
        return search_inventory(tool_input['query'])
    elif tool_name == "get_container":
        return get_container(tool_input['container_id'])
    elif tool_name == "list_containers":
        return list_containers(
            parent=tool_input.get('parent'),
            tags=tool_input.get('tags'),
            prefix=tool_input.get('prefix')
        )
    elif tool_name == "add_item":
        return add_item_to_container(
            container_id=tool_input['container_id'],
            item_description=tool_input['item_description'],
            tags=tool_input.get('tags')
        )
    elif tool_name == "remove_item":
        return remove_item_from_container(
            container_id=tool_input['container_id'],
            item_description=tool_input['item_description']
        )
    else:
        return {"error": f"Unknown tool: {tool_name}"}


@app.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage) -> ChatResponse:
    """Handle chat messages and return Claude's response."""

    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY environment variable not set"
        )

    if not inventory_data:
        raise HTTPException(
            status_code=500,
            detail="Inventory data not loaded. Ensure inventory.json exists in the current directory."
        )

    # Initialize Claude client
    client = anthropic.Anthropic(api_key=api_key)

    # System prompt with inventory context
    system_prompt = f"""You are a helpful assistant for managing a personal inventory system.

The inventory contains {len(inventory_data.get('containers', []))} containers with various items stored in them.

You have access to tools to:
- Search and query the inventory
- Get container details
- List containers
- **Add items** to containers
- **Remove items** from containers

When users ask about their inventory:
1. Use the appropriate tools to find information
2. Provide clear, concise answers
3. Reference specific container IDs when relevant
4. If items are in multiple containers, list them all
5. Be conversational and helpful
6. Match the user's language (respond in the same language they use)

When users want to modify the inventory:
1. Confirm what they want to do
2. Use add_item or remove_item tools
3. Confirm the change was successful

Important notes:
- Container IDs like A23, H11, C04 refer to physical boxes/containers
- Tags help categorize items (e.g., tag:winter, tag:sport)
- Some containers have parent locations (e.g., Garasje=garage, Loft=attic)
"""

    # Create messages array
    messages = [{"role": "user", "content": message.message}]

    # Initial API call (use model from request)
    response = client.messages.create(
        model=message.model,
        max_tokens=4096,
        tools=INVENTORY_TOOLS,
        system=system_prompt,
        messages=messages
    )

    # Handle tool use loop
    while response.stop_reason == "tool_use":
        # Extract tool calls
        tool_results = []

        for block in response.content:
            if block.type == "tool_use":
                tool_result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(tool_result)
                })

        # Add assistant response and tool results to messages
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        # Continue conversation
        response = client.messages.create(
            model=message.model,
            max_tokens=4096,
            tools=INVENTORY_TOOLS,
            system=system_prompt,
            messages=messages
        )

    # Extract final text response
    final_response = ""
    for block in response.content:
        if hasattr(block, "text"):
            final_response += block.text

    return ChatResponse(
        response=final_response,
        conversation_id=message.conversation_id or "default"
    )


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {
        "status": "ok",
        "inventory_loaded": inventory_data is not None,
        "container_count": len(inventory_data.get('containers', [])) if inventory_data else 0
    }


if __name__ == "__main__":
    import uvicorn

    print("🤖 Starting Inventory Chatbot Server...")
    print("📍 Server will run at: http://localhost:8765")
    print("💬 Chat endpoint: http://localhost:8765/chat")
    print("❤️  Health check: http://localhost:8765/health")
    print()
    print("Make sure ANTHROPIC_API_KEY is set in your environment!")
    print()

    uvicorn.run(app, host="0.0.0.0", port=8765)
