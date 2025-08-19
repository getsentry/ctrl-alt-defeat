# Item Definition Sync Guide

## Overview
This guide explains best practices for keeping item definitions (size, icon, animations, etc.) synchronized between the server and client in the autobattler game.

## Current Architecture

### Server (Python)
- **Location**: `/server/data/items/*.json`
- **Format**: JSON files categorized by type (problems, defenses, infrastructure, consumables)
- **Structure**: Defines gameplay mechanics (damage, cooldowns, CPU costs, triggers, effects)
- **Source of Truth**: Server is authoritative for gameplay stats

### Client (Godot)
- **Location**: `/client/items/sentry_items.json`
- **Format**: Single JSON file with visual/UI properties
- **Structure**: Defines visual properties (icons, dimensions, animations)
- **Purpose**: UI representation and client-side validation

## Best Practices

### 1. Single Source of Truth Pattern
Use a unified item definition format that both server and client can consume:

```json
{
  "item_id": "null_pointer",
  "gameplay": {
    "name": "Null Pointer Exception",
    "category": "problem",
    "rarity": "common",
    "triggers": [...],
    "effects": [...]
  },
  "visual": {
    "icon": "null_pointer.png",
    "shape": {"width": 1, "height": 1},
    "animations": {
      "activate": "flash_red",
      "hit": "crash_effect"
    }
  },
  "economy": {
    "base_cost": 3,
    "sell_value": 1
  }
}
```

### 2. Automatic Sync System

#### Option A: Build-Time Generation
Generate client-side definitions from server data during build:

```python
# scripts/generate_client_items.py
import json

def generate_client_items():
    server_items = load_server_items()
    client_items = {}

    for item_id, item_data in server_items.items():
        client_items[item_id] = {
            "name": item_data["name"],
            "category": item_data["category"],
            "rarity": item_data["rarity"],
            "shape": item_data.get("shape", "1x1"),
            "icon": f"res://assets/items/{item_id}.png"
        }

    save_client_items(client_items)
```

#### Option B: Runtime Sync
Server sends item catalog on session start:

```python
# server/main.py
@app.post("/session/start")
async def start_session():
    return {
        "item_catalog": get_complete_item_catalog(),
        # ... other session data
    }

def get_complete_item_catalog():
    """Returns full item definitions including visual properties"""
    catalog = {}
    for item_id, item_spec in ITEM_CATALOG.items():
        catalog[item_id] = {
            "gameplay": extract_gameplay_data(item_spec),
            "visual": get_visual_properties(item_id),
            "economy": get_economy_data(item_id)
        }
    return catalog
```

### 3. Shared Definition Schema

Create a shared schema that both systems understand:

```yaml
# shared/schemas/item_definition.yaml
ItemDefinition:
  id: string
  name: string
  category: enum[problem, defense, infrastructure, consumable]
  rarity: enum[common, uncommon, rare, epic, legendary, godly]
  shape:
    width: integer
    height: integer
  visual:
    icon_path: string
    animations: object
  gameplay:
    triggers: array
    effects: array
```

### 4. Version Control Strategy

Include version numbers to handle updates:

```json
{
  "version": "1.2.0",
  "items": {...},
  "last_modified": "2024-01-19T10:00:00Z"
}
```

Client checks version on startup:
```gdscript
func check_item_definitions():
    var local_version = load_local_version()
    var server_version = await api.get_item_version()

    if server_version > local_version:
        var new_catalog = await api.get_item_catalog()
        save_item_catalog(new_catalog)
```

### 5. Validation System

Implement validation on both sides:

```python
# server/item_validator.py
def validate_item_consistency():
    """Ensure all items have required properties"""
    for item_id, item_data in ITEM_CATALOG.items():
        assert item_data.get("name"), f"Missing name: {item_id}"
        assert item_data.get("shape"), f"Missing shape: {item_id}"
        assert item_data.get("category"), f"Missing category: {item_id}"
```

```gdscript
# client/scripts/ItemValidator.gd
func validate_item_data(item_data: Dictionary) -> bool:
    return item_data.has("name") and \
           item_data.has("shape") and \
           item_data.has("icon")
```

### 6. Asset Pipeline

For icons and animations, use consistent naming:

```
/assets/items/
  /icons/
    null_pointer.png
    memory_leak.png
  /animations/
    null_pointer_activate.tres
    memory_leak_activate.tres
```

### 7. Development Workflow

1. **Define item in shared format** (e.g., `/shared/items/new_item.json`)
2. **Run sync script** to generate server and client versions
3. **Create visual assets** following naming convention
4. **Test both server mechanics and client visuals**
5. **Version bump** when releasing

### 8. Error Handling

Handle missing or mismatched items gracefully:

```gdscript
func get_item_visual(item_id: String) -> Dictionary:
    if not item_catalog.has(item_id):
        push_warning("Unknown item: " + item_id)
        return get_placeholder_visual()
    return item_catalog[item_id].visual
```

## Implementation Recommendations

### Immediate Steps
1. Consolidate item definitions into a single shared format
2. Create a build script to generate platform-specific files
3. Add validation tests to CI/CD pipeline

### Long-term Goals
1. Move to a database-driven system for easier updates
2. Implement hot-reloading of item definitions
3. Create an item editor tool that outputs to both formats

## Example Implementation

Here's a complete example of a sync system:

```python
# scripts/sync_items.py
#!/usr/bin/env python3
import json
import os
from pathlib import Path

def load_master_items():
    """Load items from master definition"""
    master_path = Path("shared/items/master_catalog.json")
    with open(master_path) as f:
        return json.load(f)

def generate_server_items(master_items):
    """Generate Python ItemSpec definitions"""
    output = []
    for item_id, item_data in master_items.items():
        output.append(f"""
    "{item_id}": ItemSpec(
        id="{item_id}",
        name="{item_data['name']}",
        category="{item_data['category']}",
        rarity="{item_data['rarity']}",
        shape=SHAPES["{item_data['shape']}"],
        triggers={json.dumps(item_data['triggers'])}
    )""")
    return output

def generate_client_items(master_items):
    """Generate Godot-compatible JSON"""
    client_items = {}
    for item_id, item_data in master_items.items():
        shape = item_data['shape'].split('x')
        client_items[item_id] = {
            "name": item_data['name'],
            "category": item_data['category'],
            "rarity": item_data['rarity'],
            "width": int(shape[0]),
            "height": int(shape[1]),
            "icon": f"res://assets/items/icons/{item_id}.png",
            "cost": item_data.get('cost', 3)
        }
    return client_items

if __name__ == "__main__":
    master = load_master_items()

    # Generate server items
    server_items = generate_server_items(master)
    # Write to server location

    # Generate client items
    client_items = generate_client_items(master)
    with open("client/items/generated_items.json", "w") as f:
        json.dump(client_items, f, indent=2)

    print(f"Synced {len(master)} items")
```

## Testing Strategy

Ensure consistency with automated tests:

```python
# tests/test_item_sync.py
def test_all_server_items_have_client_visuals():
    server_items = load_server_items()
    client_items = load_client_items()

    for item_id in server_items:
        assert item_id in client_items, f"Missing client visual: {item_id}"
        assert client_items[item_id].get("icon"), f"Missing icon: {item_id}"
```

## Conclusion

By following these practices, you can maintain consistency between server and client item definitions while allowing each system to optimize for its specific needs. The key is establishing a single source of truth and automating the synchronization process.
