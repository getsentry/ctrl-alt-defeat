# Server Room Design - True Backpack Battles Style

## Overview
This implementation properly mimics Backpack Battles' bag system:
- **Server Room** = The inventory area (like the backpack space)
- **Servers** = Bags that create grid spaces
- **Items** = Components that can ONLY be placed inside servers

## Key Concept
Just like in Backpack Battles where you place bags to create inventory space, here you place **servers** in the server room to create grid spaces where items can go.

## Architecture

### Server Room (12x8 grid)
- The main container area where servers are placed
- Shows as a faint grid outline
- Servers can be placed anywhere in this space

### Servers (Grid Containers)
Different server types create different grid shapes:

1. **Rack Server** (2x3) - Creates 2x3 grid
2. **Blade Server** (3x2) - Creates 3x2 grid
3. **Tower Server** (1x4) - Creates 1x4 grid
4. **Mini Server** (2x2) - Creates 2x2 grid
5. **Mainframe** (4x3) - Creates 4x3 grid

### Items (Components)
Can ONLY be placed inside servers:
- **CPU Upgrade** (1x1) - Attack boost
- **RAM Module** (2x1) - Defense boost
- **Firewall** (1x2) - High defense
- **Load Balancer** (2x2) - Balanced stats
- **Cooling Fan** (1x1) - Healing
- **Storage Array** (3x1) - Defense

## Game Flow

1. **Start with empty server room** - Just a 12x8 grid outline
2. **Buy servers first** - Creates grid spaces
3. **Buy items** - Can only place in server grids
4. **Strategic placement** - Optimize server layout for items

## Visual Design

### Server Room
```
┌────────────────────────────┐
│ ░░░░░░░░░░░░░░░░░░░░░░░░░ │  <- Faint grid
│ ░░░░░░░░░░░░░░░░░░░░░░░░░ │
│ ░░░░░░░░░░░░░░░░░░░░░░░░░ │
└────────────────────────────┘
```

### Server Placed
```
┌────────────────────────────┐
│ ░░░┌─────┐░░░░░░░░░░░░░░░ │
│ ░░░│▓▓▓▓▓│░░░░░░░░░░░░░░░ │  <- Server with internal grid
│ ░░░│▓▓▓▓▓│░░░░░░░░░░░░░░░ │
│ ░░░└─────┘░░░░░░░░░░░░░░░ │
└────────────────────────────┘
```

### Items in Server
```
┌────────────────────────────┐
│ ░░░┌─────┐░░░░░░░░░░░░░░░ │
│ ░░░│█▓▓▓▓│░░░░░░░░░░░░░░░ │  <- Items (█) inside server grid
│ ░░░│██▓▓▓│░░░░░░░░░░░░░░░ │
│ ░░░└─────┘░░░░░░░░░░░░░░░ │
└────────────────────────────┘
```

## Implementation Details

### Data Structure
```gdscript
# Room grid tracks servers
room_grid[y][x] = server_reference or null

# Each server has its own internal grid
server.internal_grid[y][x] = item_reference or null
```

### Shop System
- Mixed shop with both servers and items
- Always shows at least 2 servers
- Items show they need to be placed in servers

### Validation
- Items check for server space, not room space
- `_find_server_with_space()` searches all servers
- Items are children of server's grid container

## Why This Design?

1. **True to Backpack Battles** - Bags create space, not the backpack itself
2. **Strategic Depth** - Server placement matters as much as item placement
3. **Thematic Fit** - Data centers have server racks that hold components
4. **Visual Clarity** - Clear distinction between containers and contents

## Next Steps (Future)
- Server synergies (adjacent servers boost each other)
- Special server types (cooling servers, power servers)
- Item effects based on server type
- Server upgrades
