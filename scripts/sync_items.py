#!/usr/bin/env python3
"""
Item Definition Synchronization Script
Generates server and client item definitions from a shared master catalog
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List

def load_server_items() -> Dict[str, Any]:
    """Load all server item definitions from JSON files"""
    items = {}
    server_data_path = Path(__file__).parent.parent / "server" / "data" / "items"

    for json_file in server_data_path.glob("*.json"):
        with open(json_file) as f:
            data = json.load(f)
            if "items" in data:
                items.update(data["items"])

    return items

def load_client_items() -> Dict[str, Any]:
    """Load client item definitions"""
    client_items_path = Path(__file__).parent.parent / "client" / "items" / "sentry_items.json"

    if client_items_path.exists():
        with open(client_items_path) as f:
            data = json.load(f)
            return data.get("items", {})

    return {}

def generate_unified_catalog() -> Dict[str, Any]:
    """Generate a unified item catalog from server definitions"""
    server_items = load_server_items()
    client_items = load_client_items()

    unified = {}

    for item_id, server_data in server_items.items():
        # Extract shape dimensions
        shape_str = server_data.get("shape", "1x1")
        shape_parts = shape_str.split("x")
        width = int(shape_parts[0]) if len(shape_parts) > 0 else 1
        height = int(shape_parts[1]) if len(shape_parts) > 1 else 1

        # Build unified item definition
        unified[item_id] = {
            "id": item_id,
            "name": server_data.get("name", item_id.replace("_", " ").title()),
            "category": server_data.get("category", "unknown"),
            "rarity": server_data.get("rarity", "common"),
            "shape": {
                "width": width,
                "height": height,
                "string": shape_str
            },
            "gameplay": {
                "triggers": server_data.get("triggers", []),
                "adjacency_bonus": server_data.get("adjacency_bonus"),
                "cost": server_data.get("cost", 3)
            },
            "visual": {
                "icon": f"res://assets/items/icons/{item_id}.png",
                "description": server_data.get("description", ""),
                # Use client data if available, otherwise generate defaults
                "animations": client_items.get(item_id, {}).get("animations", {
                    "activate": f"{item_id}_activate",
                    "hit": f"{item_id}_hit"
                })
            }
        }

    return unified

def generate_client_json(unified_catalog: Dict[str, Any]) -> Dict[str, Any]:
    """Generate client-compatible JSON from unified catalog"""
    client_items = {}

    for item_id, item_data in unified_catalog.items():
        # Extract key stats from triggers for display
        min_damage = 0
        max_damage = 0
        cooldown = 0
        cpu_cost = 0

        for trigger in item_data["gameplay"].get("triggers", []):
            if trigger.get("type") == "timer":
                cooldown = trigger.get("cooldown", 0)
                cpu_cost = trigger.get("cpu_cost", 0)

                for effect in trigger.get("effects", []):
                    if effect.get("type") == "attack":
                        min_damage = effect.get("min_damage", 0)
                        max_damage = effect.get("max_damage", 0)

        client_items[item_id] = {
            "name": item_data["name"],
            "description": item_data["visual"]["description"],
            "category": item_data["category"],
            "rarity": item_data["rarity"],
            "icon": item_data["visual"]["icon"],
            "width": item_data["shape"]["width"],
            "height": item_data["shape"]["height"],
            "cost": item_data["gameplay"]["cost"],
            # Include gameplay stats for UI display
            "min_damage": min_damage,
            "max_damage": max_damage,
            "cooldown": cooldown,
            "cpu_cost": cpu_cost,
            "animations": item_data["visual"]["animations"]
        }

    return {"items": client_items, "version": "1.0.0"}

def validate_consistency(unified_catalog: Dict[str, Any]) -> List[str]:
    """Validate item definitions for consistency"""
    issues = []

    for item_id, item_data in unified_catalog.items():
        # Check required fields
        if not item_data.get("name"):
            issues.append(f"{item_id}: Missing name")

        if not item_data.get("category"):
            issues.append(f"{item_id}: Missing category")

        if not item_data.get("shape"):
            issues.append(f"{item_id}: Missing shape")

        # Check visual assets exist (in a real implementation)
        icon_path = item_data["visual"]["icon"]
        # Would check if file exists in real implementation

        # Validate gameplay data
        if not item_data["gameplay"].get("triggers"):
            issues.append(f"{item_id}: No triggers defined")

    return issues

def write_generated_files(unified_catalog: Dict[str, Any]):
    """Write generated files to appropriate locations"""
    script_dir = Path(__file__).parent

    # Generate and write client JSON
    client_json = generate_client_json(unified_catalog)
    client_output_path = script_dir.parent / "client" / "items" / "generated_items.json"
    client_output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(client_output_path, "w") as f:
        json.dump(client_json, f, indent=2)

    print(f"✓ Generated client items: {client_output_path}")

    # Write unified catalog for reference
    unified_output_path = script_dir / "unified_item_catalog.json"
    with open(unified_output_path, "w") as f:
        json.dump(unified_catalog, f, indent=2)

    print(f"✓ Generated unified catalog: {unified_output_path}")

def main():
    """Main sync process"""
    print("Starting item synchronization...")

    # Generate unified catalog
    unified_catalog = generate_unified_catalog()
    print(f"Loaded {len(unified_catalog)} items")

    # Validate consistency
    issues = validate_consistency(unified_catalog)
    if issues:
        print("\n⚠ Validation issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✓ All items validated successfully")

    # Write generated files
    write_generated_files(unified_catalog)

    # Print summary
    print(f"\n✅ Synchronization complete!")
    print(f"   Total items: {len(unified_catalog)}")

    # Show item categories
    categories = {}
    for item in unified_catalog.values():
        cat = item["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print("\n   Items by category:")
    for cat, count in sorted(categories.items()):
        print(f"     - {cat}: {count}")

if __name__ == "__main__":
    main()
