#!/usr/bin/env python3
"""Create placeholder PNG graphics for the game"""

from PIL import Image, ImageDraw, ImageFont
import os

# Create directories
os.makedirs("client/assets/sprites/items", exist_ok=True)
os.makedirs("client/assets/sprites/ui", exist_ok=True)
os.makedirs("client/assets/sprites/backgrounds", exist_ok=True)

def create_item_icon(name, color, symbol, filename):
    """Create a 64x64 item icon"""
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background square
    draw.rounded_rectangle([4, 4, 60, 60], radius=8, fill=color, outline=(255, 255, 255, 100), width=2)

    # Symbol/text
    try:
        # Try to use a font if available
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except:
        font = ImageFont.load_default()

    # Get text bbox for centering
    bbox = draw.textbbox((0, 0), symbol, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (64 - text_width) // 2
    y = (64 - text_height) // 2

    draw.text((x, y), symbol, fill=(255, 255, 255, 255), font=font)

    img.save(f"client/assets/sprites/items/{filename}.png")
    print(f"Created {filename}.png")

def create_ui_element(name, size, color, filename):
    """Create UI element"""
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Panel background
    draw.rounded_rectangle([2, 2, size[0]-2, size[1]-2], radius=6,
                          fill=color, outline=(100, 100, 150, 200), width=2)

    img.save(f"client/assets/sprites/ui/{filename}.png")
    print(f"Created {filename}.png")

def create_background():
    """Create main background"""
    img = Image.new('RGBA', (1280, 720), (10, 10, 20, 255))
    draw = ImageDraw.Draw(img)

    # Add grid pattern
    for x in range(0, 1280, 40):
        draw.line([(x, 0), (x, 720)], fill=(30, 30, 50, 50), width=1)
    for y in range(0, 720, 40):
        draw.line([(0, y), (1280, y)], fill=(30, 30, 50, 50), width=1)

    img.save("client/assets/sprites/backgrounds/main_bg.png")
    print("Created main_bg.png")

# Create item icons
items = [
    ("bug_icon", (150, 50, 50, 200), "!", "bug_icon"),
    ("shield_icon", (50, 100, 200, 200), "S", "shield_icon"),
    ("gear_icon", (50, 150, 50, 200), "G", "gear_icon"),
    ("memory_leak", (150, 50, 150, 200), "M", "memory_leak"),
    ("database", (200, 120, 50, 200), "D", "database"),
    ("firewall", (200, 100, 50, 200), "F", "firewall"),
    ("coffee", (120, 80, 40, 200), "C", "coffee"),
    ("network", (50, 100, 150, 200), "N", "network"),
]

for name, color, symbol, filename in items:
    create_item_icon(name, color, symbol, filename)

# Create UI elements
create_ui_element("panel_bg", (320, 600), (20, 20, 30, 180), "panel_bg")
create_ui_element("slot_empty", (80, 80), (15, 15, 25, 100), "slot_empty")
create_ui_element("button", (120, 40), (40, 40, 60, 200), "button")

# Create background
create_background()

print("\nAll placeholder graphics created!")
