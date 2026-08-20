extends GutTest
# How big the window was left, remembered between runs.
#
# The window itself cannot be resized in a test -- headless has none -- so what
# is checked here is what would be written down and what would be asked for.

const WindowSize = preload("res://scripts/window_size.gd")


func test_the_web_has_no_window_of_its_own_to_remember():
	# A page decides how big a web build is. Asking for a size there would be
	# the game resizing somebody's browser tab.
	assert_false(WindowSize.remembers(true), "The web remembers nothing")
	assert_true(WindowSize.remembers(false), "A desktop window is the game's own")


func test_a_size_is_brought_down_to_the_screen_it_has_to_fit():
	# The screen it is opened on today may be smaller than the one it was
	# sized on, and a window bigger than the screen cannot be resized back.
	var asked := WindowSize.fits(Vector2i(3000, 2000), Vector2i(1920, 1080))

	assert_eq(asked, Vector2i(1920, 1080), "It should fit the screen it is on")


func test_a_size_that_already_fits_is_left_alone():
	assert_eq(WindowSize.fits(Vector2i(1400, 875), Vector2i(1920, 1080)),
		Vector2i(1400, 875), "Nothing to bring down")


func test_a_window_dragged_shut_is_not_worth_putting_back():
	# Nothing, so the project's own size is used instead. The game is laid out
	# in one 1680 by 1050 space and is unusable in a sliver.
	assert_eq(WindowSize.fits(Vector2i(200, 120), Vector2i(1920, 1080)),
		Vector2i.ZERO, "A sliver is not a size somebody chose")


func test_nothing_written_down_yet_asks_for_nothing():
	assert_eq(WindowSize.remembered(ConfigFile.new()), Vector2i.ZERO,
		"A first run has no size to put back")


func test_what_is_written_down_is_what_comes_back():
	var config := ConfigFile.new()

	WindowSize.remember(config, Vector2i(1200, 800), false)

	assert_eq(WindowSize.remembered(config), Vector2i(1200, 800),
		"The size it was left at")
	assert_false(config.get_value(WindowSize.SECTION, "maximised"),
		"and that it was not maximised")


func test_a_maximised_window_does_not_write_over_the_size_it_had():
	# It measures as big as the screen. Put back next time, that gives a window
	# filling the screen without being maximised, which cannot be put back to
	# the size it was before.
	var config := ConfigFile.new()
	WindowSize.remember(config, Vector2i(1200, 800), false)

	WindowSize.remember(config, Vector2i(1920, 1080), true)

	assert_eq(WindowSize.remembered(config), Vector2i(1200, 800),
		"The size it had before it was maximised")
	assert_true(config.get_value(WindowSize.SECTION, "maximised"),
		"and that it should open maximised again")
