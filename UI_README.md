# Sentry Autobattler - Visual UI System

## 🎮 Overview
Complete visual drag-and-drop UI system for the Sentry Autobattler game, working standalone with dummy data (no server required).

## ✨ Features

### Visual Systems
- **Full Drag & Drop**: Items can be dragged between shop, holding area, and inventory
- **Three-Panel Layout**:
  - **Shop** (left): Browse and purchase items
  - **Holding Area** (middle): Store purchased items before placement
  - **Inventory Grid** (right): 7x9 battle grid for strategic placement

### Animations & Effects
- **Purchase animations** with particle effects
- **Smooth transitions** for all interactions
- **Hover effects** on all interactive elements
- **Grid appearance animation** on startup
- **Gold counter animation** when spending
- **Welcome screen** animation
- **Battle start** animation

### Item System
- **8 Different item types** with unique properties:
  - Problems (Weapons): Null Pointer, Memory Leak, SQL Injection
  - Defense (Shields): Error Shield, Firewall
  - Infrastructure: Load Balancer, Redis Cache
  - Food: Coffee for energy
- **Rarity system** with color coding
- **Visual icons** for each item type
- **Dynamic stats display** (damage, cooldown, CPU cost)

## 🚀 How to Run

### Standalone Mode (No Server Required)
1. Open Godot 4.3
2. Open the project from `client/` directory
3. Run the scene: `scenes/EnhancedGame.tscn`

The game will start with:
- 25 starting gold
- Pre-populated shop with random items
- Full drag-and-drop functionality

## 🎯 How to Play

### Game Flow
1. **Shop Phase**:
   - Browse 5 random items in the shop
   - Click buy button (shows cost in gold)
   - Purchased items appear in holding area

2. **Organize Items**:
   - Drag items from holding area to inventory grid
   - Items snap to grid positions
   - Visual feedback shows valid placement

3. **Battle**:
   - Click "Start Battle" when ready
   - Battle animation plays
   - (Currently simulated - will connect to server later)

### Controls
- **Left Click + Drag**: Move items
- **Hover**: See item highlights
- **Buy Button**: Purchase from shop
- **Refresh Shop**: Get new items (costs 2 gold)

## 📁 File Structure

```
client/
├── scenes/
│   ├── EnhancedGame.tscn      # Main enhanced UI scene
│   └── StandaloneGame.tscn    # Basic UI scene
├── scripts/
│   ├── DraggableItem.gd       # Draggable item component
│   ├── GameUI.gd              # Basic game UI
│   └── EnhancedGameUI.gd      # Enhanced UI with animations
└── project.godot               # Godot project file
```

## 🎨 Visual Features

### Color Coding
- **Common** (Gray): Basic items
- **Uncommon** (Green): Better stats
- **Rare** (Blue): Strong effects
- **Epic** (Purple): Powerful abilities
- **Legendary** (Orange): Top tier

### Animations
- Items scale on hover
- Smooth drag with semi-transparency
- Slot highlighting during drag
- Purchase particles
- Gold counter tweening
- Grid slots appear with stagger effect

## 🔧 Customization

### Adding New Items
Edit the `ITEM_TEMPLATES` array in `EnhancedGameUI.gd`:
```gdscript
{
    "name": "Your Item",
    "category": "problem/defense/infrastructure",
    "rarity": "common/uncommon/rare/epic",
    "cost": 5,
    "damage": "4-8",  # Optional
    "icon": "🔥",
    "color": Color(r, g, b)
}
```

### Modifying Grid Size
Change `INVENTORY_SLOT_SIZE` and grid dimensions in the script.

## 🚧 Next Steps

### To Add Graphics
1. Replace placeholder icons in `DraggableItem.gd`
2. Add sprite textures to `assets/sprites/`
3. Update `_create_placeholder_icon()` to use real sprites

### To Connect Server
1. Uncomment server API calls
2. Replace dummy data with real item catalog
3. Connect battle simulation to server endpoint

## 🎮 Current Status
✅ **Fully Functional Standalone UI** with:
- Complete drag-and-drop system
- Visual feedback and animations
- Shop, holding area, and inventory grid
- Dummy data for testing
- Ready for real graphics integration

The UI is now ready for graphics! Just provide the sprite assets and they can be easily integrated into the existing system.
