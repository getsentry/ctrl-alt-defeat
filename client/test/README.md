# Autobattler Test Suite

This project uses **GUT (Godot Unit Test)** framework for testing, similar to pytest for Python or Jest for JavaScript.

## Running Tests

### Run All Tests (Similar to `pytest`)
```bash
./run_tests.sh
```

### Run Specific Test File
```bash
godot --headless -s addons/gut/gut_cmdln.gd -gtest=res://test/unit/test_game_state_manager.gd -gexit
```

### Run Specific Test Method
```bash
godot --headless -s addons/gut/gut_cmdln.gd -gtest=res://test/unit/test_game_state_manager.gd -gunit_test_name=test_starting_containers_property_exists -gexit
```

## Writing Tests

### Basic Test Structure
```gdscript
extends GutTest

func before_all():
    # Runs once before all tests in this file
    pass

func before_each():
    # Runs before each test method
    GameStateManager.start_new_game()

func after_each():
    # Runs after each test method
    pass

func after_all():
    # Runs once after all tests in this file
    pass

func test_something():
    # Test methods must start with "test_"
    assert_eq(actual, expected, "Optional failure message")
```

### Available Assertions

- `assert_eq(actual, expected, msg="")` - Assert values are equal
- `assert_ne(actual, expected, msg="")` - Assert values are not equal
- `assert_true(condition, msg="")` - Assert condition is true
- `assert_false(condition, msg="")` - Assert condition is false
- `assert_null(value, msg="")` - Assert value is null
- `assert_not_null(value, msg="")` - Assert value is not null
- `assert_gt(actual, expected, msg="")` - Assert actual > expected
- `assert_lt(actual, expected, msg="")` - Assert actual < expected
- `assert_gte(actual, expected, msg="")` - Assert actual >= expected
- `assert_lte(actual, expected, msg="")` - Assert actual <= expected
- `assert_between(value, min, max, msg="")` - Assert value is between min and max
- `assert_has(container, value, msg="")` - Assert container has value
- `assert_does_not_have(container, value, msg="")` - Assert container doesn't have value
- `assert_string_contains(text, substring, msg="")` - Assert string contains substring
- `assert_string_starts_with(text, prefix, msg="")` - Assert string starts with prefix
- `assert_string_ends_with(text, suffix, msg="")` - Assert string ends with suffix
- `assert_almost_eq(actual, expected, tolerance, msg="")` - Assert floats are nearly equal
- `assert_almost_ne(actual, expected, tolerance, msg="")` - Assert floats are not nearly equal

### Signal Testing
```gdscript
func test_signal_emitted():
    watch_signals(my_object)
    my_object.do_something()
    assert_signal_emitted(my_object, "my_signal")
    assert_signal_emitted_with_parameters(my_object, "my_signal", [param1, param2])
```

### Mocking/Doubling
```gdscript
func test_with_mock():
    var mock = double(MyClass)
    stub(mock, "method_name").to_return(42)
    assert_eq(mock.method_name(), 42)
```

## Test Organization

```
test/
├── unit/                   # Unit tests
│   ├── test_game_state_manager.gd
│   ├── test_inventory_persistence.gd
│   ├── test_starting_containers_bug.gd
│   └── test_complete_flow.gd
├── integration/           # Integration tests (future)
└── README.md             # This file
```

## Configuration

Tests are configured via `.gutconfig.json` in the project root. Key settings:

- `dirs`: Directories to search for tests
- `test_prefix`: Test method prefix (default: "test_")
- `should_exit`: Exit after running tests
- `log_level`: Verbosity of output

## CI/CD Integration

The test runner returns proper exit codes:
- 0: All tests passed
- Non-zero: Tests failed

Example GitHub Actions:
```yaml
- name: Run Tests
  run: |
    cd client
    ./run_tests.sh
```

## Debugging Tests

To run tests with GUI (not headless):
```bash
godot -s addons/gut/gut_cmdln.gd -gdir=res://test
```

## Test Coverage

GUT doesn't provide built-in coverage reporting, but you can:
1. Use the GUI to see which tests ran
2. Check the test summary output
3. Implement custom coverage tracking if needed

## Best Practices

1. **Use `before_each()`** to reset state between tests
2. **Keep tests isolated** - each test should be independent
3. **Use descriptive test names** - `test_inventory_cleared_on_new_game()` not `test_1()`
4. **One assertion per test** when possible (or related assertions)
5. **Test edge cases** - empty arrays, null values, boundary conditions
6. **Mock external dependencies** when testing units in isolation
7. **Use meaningful assertion messages** to help debug failures

## Common Patterns

### Testing Singletons
```gdscript
func before_each():
    GameStateManager.start_new_game()  # Reset singleton state

func test_singleton_behavior():
    GameStateManager.gold = 100
    assert_eq(GameStateManager.gold, 100)
```

### Testing Scene Loading
```gdscript
func test_scene_loads():
    var scene = load("res://scenes/MainMenu.tscn")
    assert_not_null(scene)
    var instance = scene.instantiate()
    assert_not_null(instance)
    instance.queue_free()
```

### Testing with Timing
```gdscript
func test_with_delay():
    yield(yield_for(2.0), YIELD)  # Wait 2 seconds
    assert_true(something_happened)
```

## Troubleshooting

### "GUT class_names have not been imported"
Run: `godot --headless --import`

### Tests not found
- Ensure test files are in directories specified in `.gutconfig.json`
- Ensure test methods start with `test_`
- Ensure test class extends `GutTest`

### Tests pass individually but fail together
- Check for shared state between tests
- Use `before_each()` to reset state
- Check for timing issues or race conditions
