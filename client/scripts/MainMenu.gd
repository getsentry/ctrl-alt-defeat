extends Control

func _ready():
	print("Main Menu starting...")
	_setup_menu()

func _setup_menu():
	# Background
	var bg = ColorRect.new()
	bg.color = Color(0.05, 0.05, 0.08, 1.0)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	# Title
	var title = Label.new()
	title.text = "SENTRY AUTOBATTLER"
	title.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	title.position = Vector2(440, 100)
	title.add_theme_font_size_override("font_size", 48)
	title.add_theme_color_override("font_color", Color(0.9, 0.9, 1.0))
	title.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.5))
	title.add_theme_constant_override("shadow_offset_x", 3)
	title.add_theme_constant_override("shadow_offset_y", 3)
	add_child(title)

	# Subtitle
	var subtitle = Label.new()
	subtitle.text = "Choose Your UI Version"
	subtitle.position = Vector2(520, 200)
	subtitle.add_theme_font_size_override("font_size", 24)
	subtitle.add_theme_color_override("font_color", Color(0.7, 0.7, 0.8))
	add_child(subtitle)

	# Simple UI Button
	var simple_btn = Button.new()
	simple_btn.text = "Simple UI\n(Basic version with visible borders)"
	simple_btn.position = Vector2(490, 300)
	simple_btn.size = Vector2(300, 80)
	simple_btn.add_theme_font_size_override("font_size", 16)

	var btn_style = StyleBoxFlat.new()
	btn_style.bg_color = Color(0.15, 0.15, 0.25, 1.0)
	btn_style.set_corner_radius_all(8)
	btn_style.set_border_width_all(2)
	btn_style.border_color = Color(0.3, 0.3, 0.4, 1.0)
	simple_btn.add_theme_stylebox_override("normal", btn_style)

	var btn_hover = btn_style.duplicate()
	btn_hover.bg_color = Color(0.2, 0.2, 0.3, 1.0)
	btn_hover.border_color = Color(0.4, 0.4, 0.5, 1.0)
	simple_btn.add_theme_stylebox_override("hover", btn_hover)

	simple_btn.pressed.connect(_load_simple_ui)
	add_child(simple_btn)

	# Improved UI Button
	var improved_btn = Button.new()
	improved_btn.text = "Improved UI\n(Polished version without bounding boxes)"
	improved_btn.position = Vector2(490, 400)
	improved_btn.size = Vector2(300, 80)
	improved_btn.add_theme_font_size_override("font_size", 16)

	var improved_style = StyleBoxFlat.new()
	improved_style.bg_color = Color(0.15, 0.25, 0.15, 1.0)
	improved_style.set_corner_radius_all(8)
	improved_style.set_border_width_all(2)
	improved_style.border_color = Color(0.3, 0.4, 0.3, 1.0)
	improved_btn.add_theme_stylebox_override("normal", improved_style)

	var improved_hover = improved_style.duplicate()
	improved_hover.bg_color = Color(0.2, 0.3, 0.2, 1.0)
	improved_hover.border_color = Color(0.4, 0.5, 0.4, 1.0)
	improved_btn.add_theme_stylebox_override("hover", improved_hover)

	improved_btn.pressed.connect(_load_improved_ui)
	add_child(improved_btn)

	# Exit Button
	var exit_btn = Button.new()
	exit_btn.text = "Exit"
	exit_btn.position = Vector2(540, 550)
	exit_btn.size = Vector2(200, 50)
	exit_btn.add_theme_font_size_override("font_size", 18)

	var exit_style = StyleBoxFlat.new()
	exit_style.bg_color = Color(0.25, 0.15, 0.15, 1.0)
	exit_style.set_corner_radius_all(5)
	exit_btn.add_theme_stylebox_override("normal", exit_style)

	var exit_hover = exit_style.duplicate()
	exit_hover.bg_color = Color(0.35, 0.2, 0.2, 1.0)
	exit_btn.add_theme_stylebox_override("hover", exit_hover)

	exit_btn.pressed.connect(_on_exit)
	add_child(exit_btn)

	# Info text
	var info = Label.new()
	info.text = "The Improved UI removes the bounding boxes and has better visual polish"
	info.position = Vector2(380, 630)
	info.add_theme_font_size_override("font_size", 14)
	info.add_theme_color_override("font_color", Color(0.6, 0.6, 0.7))
	add_child(info)

	print("Main menu ready")

func _load_simple_ui():
	print("Loading Simple UI...")
	get_tree().change_scene_to_file("res://scenes/SimpleTest.tscn")

func _load_improved_ui():
	print("Loading Improved UI...")
	get_tree().change_scene_to_file("res://scenes/ImprovedUI.tscn")

func _on_exit():
	get_tree().quit()
