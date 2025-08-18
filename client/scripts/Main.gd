extends Control

@onready var game_manager: Node = $GameManager
@onready var server_api = $ServerAPI

@onready var main_menu: VBoxContainer = $MainMenu
@onready var shop_screen: Control = $ShopScreen
@onready var battle_screen: Control = $BattleScreen
@onready var game_over_screen: Control = $GameOverScreen
@onready var win_screen: Control = $WinScreen

@onready var round_label: Label = $ShopScreen/TopBar/RoundLabel
@onready var gold_label: Label = $ShopScreen/TopBar/GoldLabel
@onready var health_label: Label = $ShopScreen/TopBar/HealthLabel
@onready var shop_items_container: HBoxContainer = $ShopScreen/ShopItems
@onready var inventory_grid: GridContainer = $ShopScreen/InventoryGrid
@onready var battle_log: RichTextLabel = $BattleScreen/BattleLog
@onready var player_health_label: Label = $BattleScreen/BattleInfo/PlayerHealth
@onready var opponent_health_label: Label = $BattleScreen/BattleInfo/OpponentHealth

var current_session: Dictionary = {}
var current_shop: Array = []
var inventory_items: Array = []
var item_catalog: Dictionary = {}
var current_round: int = 1
var wins: int = 0
var player_health: int = 25

func _ready():
	_connect_signals()
	_hide_all_screens()
	main_menu.visible = true

	_setup_inventory_grid()

func _connect_signals():
	$MainMenu/StartButton.pressed.connect(_on_start_button_pressed)
	$MainMenu/QuitButton.pressed.connect(_on_quit_button_pressed)
	$ShopScreen/ActionButtons/RefreshButton.pressed.connect(_on_refresh_shop_pressed)
	$ShopScreen/ActionButtons/StartBattleButton.pressed.connect(_on_start_battle_pressed)
	$GameOverScreen/GameOverInfo/RestartButton.pressed.connect(_on_restart_pressed)
	$GameOverScreen/GameOverInfo/MainMenuButton.pressed.connect(_on_main_menu_pressed)
	$WinScreen/WinInfo/ContinueButton.pressed.connect(_on_continue_pressed)
	$WinScreen/WinInfo/MainMenuButton.pressed.connect(_on_main_menu_pressed)

	server_api.game_started.connect(_on_game_started)
	server_api.shop_received.connect(_on_shop_received)
	server_api.battle_complete.connect(_on_battle_complete)
	server_api.error_occurred.connect(_on_error_occurred)

func _hide_all_screens():
	main_menu.visible = false
	shop_screen.visible = false
	battle_screen.visible = false
	game_over_screen.visible = false
	win_screen.visible = false

func _setup_inventory_grid():
	inventory_grid.columns = 7
	for y in range(9):
		for x in range(7):
			var slot = Button.new()
			slot.custom_minimum_size = Vector2(80, 80)
			slot.text = ""
			slot.set_meta("grid_pos", Vector2i(x, y))
			slot.pressed.connect(_on_inventory_slot_clicked.bind(slot))
			inventory_grid.add_child(slot)

func _on_start_button_pressed():
	print("Starting new game...")
	server_api.start_new_game()

func _on_quit_button_pressed():
	get_tree().quit()

func _on_game_started(player_id: String, game_data: Dictionary):
	print("Game started with player ID: ", player_id)
	current_session = game_data.get("session", {})
	item_catalog = game_data.get("item_catalog", {})

	current_round = current_session.get("round", 1)
	wins = 0
	player_health = 25 if current_round <= 3 else 35 if current_round <= 6 else 50 if current_round <= 9 else 75 if current_round <= 12 else 100 if current_round <= 15 else 150

	_update_ui()
	_show_shop()

func _show_shop():
	_hide_all_screens()
	shop_screen.visible = true

	if current_session.has("current_shop"):
		_display_shop(current_session["current_shop"])

func _update_ui():
	round_label.text = "Round " + str(current_round)
	gold_label.text = "Gold: " + str(current_session.get("gold", 0))
	health_label.text = "Health: " + str(player_health)

func _display_shop(shop_data: Array):
	current_shop = shop_data

	for child in shop_items_container.get_children():
		child.queue_free()

	for i in range(shop_data.size()):
		var item_panel = Panel.new()
		item_panel.custom_minimum_size = Vector2(180, 120)

		var vbox = VBoxContainer.new()
		item_panel.add_child(vbox)

		if shop_data[i] != null:
			var item_data = shop_data[i]

			var name_label = Label.new()
			name_label.text = item_data.get("name", "Unknown")
			name_label.add_theme_font_size_override("font_size", 14)
			vbox.add_child(name_label)

			var type_label = Label.new()
			type_label.text = item_data.get("category", "")
			type_label.add_theme_font_size_override("font_size", 12)
			vbox.add_child(type_label)

			var stats_label = Label.new()
			if item_data.has("min_damage"):
				stats_label.text = "DMG: %d-%d" % [item_data.get("min_damage", 0), item_data.get("max_damage", 0)]
			else:
				stats_label.text = item_data.get("special_effect", "")
			stats_label.add_theme_font_size_override("font_size", 10)
			vbox.add_child(stats_label)

			var cost_label = Label.new()
			cost_label.text = "Cost: " + str(item_data.get("cost", 0)) + " Gold"
			cost_label.add_theme_font_size_override("font_size", 12)
			vbox.add_child(cost_label)

			var buy_button = Button.new()
			buy_button.text = "Buy"
			buy_button.pressed.connect(_on_buy_item_pressed.bind(item_data))
			vbox.add_child(buy_button)
		else:
			var empty_label = Label.new()
			empty_label.text = "Empty Slot"
			vbox.add_child(empty_label)

		shop_items_container.add_child(item_panel)

func _on_buy_item_pressed(item_data: Dictionary):
	var cost = item_data.get("cost", 0)
	var current_gold = current_session.get("gold", 0)

	if current_gold >= cost:
		print("Buying item: ", item_data.get("name"))

		current_session["gold"] -= cost

		var new_item = {
			"id": item_data.get("id"),
			"item_type": item_data.get("item_type"),
			"name": item_data.get("name"),
			"position": null,
			"tier": item_data.get("tier", 1)
		}
		inventory_items.append(new_item)

		for i in range(current_shop.size()):
			if current_shop[i] != null and current_shop[i].get("id") == item_data.get("id"):
				current_shop[i] = null
				break

		_update_ui()
		_display_shop(current_shop)
		_update_inventory_display()

		server_api.purchase_item(item_data.get("id"))
	else:
		print("Not enough gold!")

func _update_inventory_display():
	for i in range(inventory_grid.get_child_count()):
		var slot = inventory_grid.get_child(i)
		slot.text = ""
		slot.modulate = Color.WHITE

	for item in inventory_items:
		if item.position != null:
			var pos = item.position
			var index = pos[1] * 7 + pos[0]
			if index < inventory_grid.get_child_count():
				var slot = inventory_grid.get_child(index)
				slot.text = item.get("name", "Item").substr(0, 8)
				slot.modulate = Color.CYAN

func _on_inventory_slot_clicked(slot: Button):
	var grid_pos = slot.get_meta("grid_pos")

	for item in inventory_items:
		if item.position == null:
			item.position = [grid_pos.x, grid_pos.y]
			_update_inventory_display()
			return

	for item in inventory_items:
		if item.position != null and item.position[0] == grid_pos.x and item.position[1] == grid_pos.y:
			if Input.is_key_pressed(KEY_SHIFT):
				var value = 5
				inventory_items.erase(item)
				current_session["gold"] += value / 2
				_update_ui()
				_update_inventory_display()
				server_api.sell_item(value)
			else:
				item.position = null
				_update_inventory_display()
			return

func _on_refresh_shop_pressed():
	if current_session.get("gold", 0) >= 2:
		print("Refreshing shop...")
		server_api.refresh_shop(current_round)

func _on_shop_received(shop_data: Dictionary):
	current_session["gold"] = shop_data.get("gold", current_session.get("gold", 0))
	_update_ui()
	_display_shop(shop_data.get("shop", []))

func _on_start_battle_pressed():
	var placed_items = []
	for item in inventory_items:
		if item.position != null:
			placed_items.append({
				"id": item.get("id"),
				"item_type": item.get("item_type"),
				"position": item.position,
				"tier": item.get("tier", 1)
			})

	if placed_items.size() == 0:
		print("Cannot start battle with no items placed!")
		return

	print("Starting battle with ", placed_items.size(), " items")
	_hide_all_screens()
	battle_screen.visible = true
	battle_log.clear()
	battle_log.append_text("Battle starting...\n")

	server_api.simulate_battle(placed_items, current_round)

func _on_battle_complete(result: Dictionary):
	print("Battle complete: ", result)

	var battle_result = result.get("battle_result", {})
	var session_update = result.get("session_update", {})
	var new_shop = result.get("new_shop", [])

	var winner = battle_result.get("winner", 0)
	var player_won = (winner == 1)

	if player_won:
		wins += 1
		battle_log.append_text("\n[color=green]VICTORY![/color]\n")
	else:
		player_health -= 10 if player_health <= 50 else 20
		battle_log.append_text("\n[color=red]DEFEAT![/color]\n")

	current_session["gold"] = session_update.get("gold", current_session.get("gold", 0))
	current_round = session_update.get("round", current_round)
	current_session["current_shop"] = new_shop

	await get_tree().create_timer(2.0).timeout

	if player_health <= 0:
		_show_game_over()
	elif wins >= 10:
		_show_win_screen()
	else:
		_show_shop()

func _show_game_over():
	_hide_all_screens()
	game_over_screen.visible = true
	$GameOverScreen/GameOverInfo/FinalScore.text = "You reached Round " + str(current_round)

func _show_win_screen():
	_hide_all_screens()
	win_screen.visible = true

func _on_restart_pressed():
	inventory_items.clear()
	current_shop.clear()
	server_api.start_new_game()

func _on_continue_pressed():
	_show_shop()

func _on_main_menu_pressed():
	inventory_items.clear()
	current_shop.clear()
	_hide_all_screens()
	main_menu.visible = true

func _on_error_occurred(message: String):
	print("Error: ", message)
	push_error(message)
