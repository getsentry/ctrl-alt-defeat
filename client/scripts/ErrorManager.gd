extends Node
const Presentation = preload("res://scripts/Presentation.gd")
# Centralized error handling and user feedback

signal error_displayed(message: String)
signal error_cleared()

var error_queue: Array = []
var current_error_ui = null
var error_display_time: float = 3.0

func _ready():
	# Connect to network errors
	if has_node("/root/BattleServerAPI"):
		BattleServerAPI.error_occurred.connect(_on_network_error)

func show_error(message: String, duration: float = 3.0):
	"""Display an error message to the user"""
	print("[ERROR] " + message)

	# Add to queue
	error_queue.append({
		"message": message,
		"duration": duration,
		"timestamp": Time.get_ticks_msec()
	})

	# Process queue if not already showing an error
	if current_error_ui == null:
		_process_error_queue()

	error_displayed.emit(message)

func show_warning(message: String, duration: float = 2.0):
	"""Display a warning message to the user"""
	print("[WARNING] " + message)
	show_error(message, duration)

func show_info(message: String, duration: float = 2.0):
	"""Display an info message to the user"""
	print("[INFO] " + message)
	# For now, treat as error but could have different UI
	show_error(message, duration)

func _process_error_queue():
	"""Process queued error messages"""
	if error_queue.is_empty():
		return

	var error_data = error_queue.pop_front()
	_display_error_ui(error_data.message, error_data.duration)

func _display_error_ui(message: String, duration: float):
	"""Create and display error UI overlay"""
	# Get current scene
	var current_scene = get_tree().current_scene
	if not current_scene:
		return

	# Create error panel
	var panel = Panel.new()
	panel.name = "ErrorPanel"
	panel.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	panel.position.y = 50
	panel.size.y = 60
	panel.modulate = Color(1, 0.3, 0.3, 0.9)

	# Add label
	var label = Label.new()
	label.text = message
	label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	label.add_theme_font_size_override("font_size", 18)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	panel.add_child(label)

	# Add to scene
	current_scene.add_child(panel)
	current_error_ui = panel

	# Animate in
	if Presentation.animations_enabled():
		var tween = get_tree().create_tween()
		panel.modulate.a = 0
		tween.tween_property(panel, "modulate:a", 0.9, 0.3)

	# Auto-hide after duration
	await get_tree().create_timer(Presentation.delay(duration)).timeout
	_hide_error_ui()

func _hide_error_ui():
	"""Hide and clean up error UI"""
	if not current_error_ui:
		return

	# Animate out
	if not Presentation.animations_enabled():
		current_error_ui.queue_free()
		current_error_ui = null
		return

	var tween = get_tree().create_tween()
	tween.tween_property(current_error_ui, "modulate:a", 0.0, 0.3)
	tween.tween_callback(func():
		if current_error_ui:
			current_error_ui.queue_free()
			current_error_ui = null
			error_cleared.emit()

			# Process next error if any
			if not error_queue.is_empty():
				_process_error_queue()
	)

func _on_network_error(message: String):
	"""Handle network-specific errors"""
	# Add context to network errors
	if "404" in message:
		show_error("Server not found. Is the server running?", 5.0)
	elif "timeout" in message.to_lower():
		show_error("Connection timed out. Check your internet connection.", 5.0)
	elif "500" in message:
		show_error("Server error. Please try again later.", 4.0)
	else:
		show_error("Network error: " + message, 4.0)

func clear_all_errors():
	"""Clear all queued and displayed errors"""
	error_queue.clear()
	if current_error_ui:
		current_error_ui.queue_free()
		current_error_ui = null
		error_cleared.emit()
