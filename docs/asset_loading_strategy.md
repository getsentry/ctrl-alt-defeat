# Asset Loading Strategy

## Recommended Approach: Hybrid Static/Dynamic

### Overview
- **Build-time**: Include all known item assets in client
- **Runtime**: Load item stats/mechanics from server
- **Updates**: New items use placeholder icons until next client update

### Implementation

#### 1. Client Asset Structure
```
/client/assets/items/
  /icons/
    # Known items (shipped with build)
    null_pointer.png
    memory_leak.png
    firewall.png

    # Category placeholders for new items
    placeholder_problem.png
    placeholder_defense.png
    placeholder_infrastructure.png

  /animations/
    # Reusable animation templates
    attack_basic.tres
    defense_basic.tres
    buff_basic.tres
```

#### 2. Server Item Definition
```json
{
  "item_id": "null_pointer",
  "name": "Null Pointer Exception",
  "stats": {...},
  "visual": {
    "icon": "null_pointer",  // Icon name, not path
    "fallback_icon": "placeholder_problem",
    "animation": "attack_basic",
    "color_tint": "#FF5555"
  }
}
```

#### 3. Client Icon Loading
```gdscript
# ItemAssetManager.gd
extends Node

const ICON_PATH = "res://assets/items/icons/"
var icon_cache = {}

func get_item_icon(item_data: Dictionary) -> Texture:
    var icon_name = item_data.visual.icon

    # Check cache
    if icon_cache.has(icon_name):
        return icon_cache[icon_name]

    # Try loading specific icon
    var icon_path = ICON_PATH + icon_name + ".png"
    if ResourceLoader.exists(icon_path):
        icon_cache[icon_name] = load(icon_path)
        return icon_cache[icon_name]

    # Fall back to category placeholder
    var fallback = item_data.visual.get("fallback_icon", "placeholder_" + item_data.category)
    var fallback_path = ICON_PATH + fallback + ".png"
    if ResourceLoader.exists(fallback_path):
        var texture = load(fallback_path)

        # Apply color tint if specified
        if item_data.visual.has("color_tint"):
            texture = apply_tint(texture, item_data.visual.color_tint)

        icon_cache[icon_name] = texture
        return texture

    # Ultimate fallback
    return preload("res://assets/items/icons/placeholder_unknown.png")

func apply_tint(texture: Texture, color: String) -> Texture:
    # Create tinted version of texture
    var image = texture.get_image()
    image.modulate = Color(color)
    return ImageTexture.create_from_image(image)
```

#### 4. Progressive Enhancement
```gdscript
# Download new assets when available (optional)
func check_for_asset_updates():
    var manifest = await api.get_asset_manifest()

    for asset in manifest.new_assets:
        if not has_asset_locally(asset.id):
            if asset.size < MAX_DOWNLOAD_SIZE:
                download_asset_background(asset)
            else:
                mark_for_next_update(asset)
```

### Benefits

1. **No Server Image Hosting**: Server only manages JSON data
2. **Instant Loading**: Most assets are local
3. **Graceful Degradation**: New items work immediately with placeholders
4. **Efficient Updates**: Only download truly new assets
5. **Offline Support**: Game works without internet after initial download

### Update Cycle

1. **Immediate** (No client update needed):
   - New items appear with placeholder icons
   - All gameplay mechanics work
   - Stats and descriptions are current

2. **Next Update** (Client update):
   - New item icons included
   - New animations added
   - Visual polish improvements

### Server Endpoints

```python
# Existing endpoint already provides this
@app.post("/session/start")
async def start_session():
    return {
        "item_catalog": get_item_catalog(),  # Full item definitions
        "asset_version": "1.2.0",  # Client can check if update needed
        "new_items_since": ["quantum_processor", "ddos_attack"]  # For UI hints
    }

# Optional: Asset manifest for progressive downloads
@app.get("/assets/manifest")
async def get_asset_manifest(client_version: str):
    return {
        "current_version": "1.2.0",
        "optional_downloads": [
            {
                "id": "quantum_processor_icon",
                "url": "https://cdn.../quantum_processor.png",
                "size": 2048,
                "checksum": "abc123"
            }
        ]
    }
```

### Visual Variety Without New Assets

Generate visual variety using existing assets:

```gdscript
func create_item_visual(item_data):
    var base_icon = get_item_icon(item_data)

    # Add rarity frame
    var frame = get_rarity_frame(item_data.rarity)

    # Add tier stars
    if item_data.tier > 1:
        add_tier_indicators(base_icon, item_data.tier)

    # Add effect particles
    if item_data.has_special_effect:
        add_particle_effect(base_icon, item_data.effect_type)

    return compose_final_icon(base_icon, frame, effects)
```

### Testing New Items

For development/testing without creating assets:

```gdscript
# Dev mode: Generate icons from text
func generate_dev_icon(item_data):
    var icon = Image.create(64, 64, false, Image.FORMAT_RGBA8)
    icon.fill(get_category_color(item_data.category))

    # Add item initials
    var initials = get_initials(item_data.name)
    draw_text_on_image(icon, initials)

    return ImageTexture.create_from_image(icon)
```

## Conclusion

This approach provides the best balance:
- **Fast iteration**: Add items server-side immediately
- **Good UX**: Items work right away, look better after updates
- **Simple deployment**: No complex CDN or image serving needed
- **Efficient bandwidth**: Only JSON data transferred during gameplay

The key insight is that **gameplay functionality is more important than perfect visuals**, so we can ship working items immediately and improve visuals in regular client updates.
