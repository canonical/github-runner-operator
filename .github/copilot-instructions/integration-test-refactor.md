# Integration Test Refactoring Instructions

## Overview

Refactor all integration tests in the `tests/integration/` directory to use functional tests instead of class-based tests, with shared fixtures moved to module level and improved naming conventions. Follow these specific guidelines for a clean, maintainable test structure.

## Refactoring Requirements

### 1. Convert All Class-Based Tests to Functions

- **Remove all test classes**: Convert `class TestSomething:` to individual `async def test_something()` functions
- **Flatten test hierarchy**: Move all test methods to module level as standalone functions
- **Preserve test logic**: Maintain existing test functionality while changing structure
- **Update test names**: Use clear, concise naming that focuses on behavior

### 2. Module-Level Resource Management

- **Use constants for static data**: Configuration values, timeouts, file paths should be module-level constants
- **Use fixtures only for resources**: Things that need setup/teardown (applications, connections, temporary resources)
- **Implement proper cleanup**: Ensure all fixtures have appropriate teardown logic
- **Optimize fixture scoping**:
  - `scope="session"` for expensive, reusable resources
  - `scope="module"` for resources shared across tests in one file
  - `scope="function"` for test-specific setup that needs isolation

### 3. Improved Test Naming Conventions

- **Focus on behavior**: What the test verifies, not how it's implemented
- **Remove redundant words**: Avoid "test*that*", "verify*", "check*", "successfully", "on_scale_down"
- **Use simple present tense**: "spawns", "cleanup", "updates" vs "spawns_successfully"
- **Be concise but clear**: `test_runner_cleanup()` instead of `test_runner_cleanup_on_scale_down()`

### 4. Coding Standards

- **No nested functions**: Keep all functions at module level
- **Comprehensive type hints**: Add type annotations to all functions and fixtures
- **Clear docstrings**: Document purpose and behavior of all tests and fixtures
- **Consistent naming**: Use descriptive, standardized naming conventions
- **DRY principle**: Extract common patterns into reusable utilities

## Refactoring Patterns

### A. Convert Class Tests to Functions with Constants

#### Before (Class-based with fixture for static data):

```python
class TestRunnerLifecycle:
    @pytest.fixture(scope="module")
    def runner_config(self) -> Dict[str, Any]:
        return {"cpu": 2, "memory": "4GB"}

    def setup_method(self):
        self.timeout = 600

    async def test_runner_spawns_successfully(self, app, runner_config):
        # Test implementation
        pass

    async def test_runner_cleanup_on_scale_down(self, app, runner_config):
        # Test implementation
        pass
```

#### After (Functional with constants and improved naming):

```python
# Module-level constants for static data
RUNNER_CONFIG = {"cpu": 2, "memory": "4GB"}
LIFECYCLE_CONFIG = {
    "reconcile-interval": "1",
    "base-virtual-machines": "0"
}
TIMEOUT_RUNNER_SPAWN = 600
TIMEOUT_CLEANUP = 300

# Fixtures only for resources needing setup/teardown
@pytest_asyncio.fixture(scope="function")
async def lifecycle_app(clean_app: Application) -> AsyncIterator[Application]:
    """Application configured for lifecycle testing."""
    await clean_app.set_config(LIFECYCLE_CONFIG)
    await wait_for_application_ready(clean_app)
    yield clean_app

# Clear, concise test names focusing on behavior
async def test_runner_spawns(
    lifecycle_app: Application,
    test_repository: Repository
) -> None:
    """
    Test that a runner spawns when requested.

    Given: An application with no active runners
    When: Setting base-virtual-machines to 1
    Then: Exactly one runner should spawn and register with GitHub
    """
    await lifecycle_app.set_config({"base-virtual-machines": "1"})

    await wait_for_runner_count(
        lifecycle_app,
        expected_count=1,
        timeout=TIMEOUT_RUNNER_SPAWN
    )

    registered_runners = await verify_runner_registration(
        test_repository,
        expected_count=1
    )

    assert len(registered_runners) == 1
    assert registered_runners[0].status == "online"

async def test_runner_cleanup(
    lifecycle_app: Application,
    test_repository: Repository
) -> None:
    """
    Test that runners are cleaned up when scaling down.

    Given: An application with one active runner
    When: Setting base-virtual-machines to 0
    Then: The runner should be removed from both Juju and GitHub
    """
    # Start with one runner
    await lifecycle_app.set_config({"base-virtual-machines": "1"})
    await wait_for_runner_count(lifecycle_app, expected_count=1)

    # Scale down to zero
    await lifecycle_app.set_config({"base-virtual-machines": "0"})

    await wait_for_runner_count(
        lifecycle_app,
        expected_count=0,
        timeout=TIMEOUT_CLEANUP
    )

    # Verify GitHub cleanup
    remaining_runners = await verify_runner_registration(
        test_repository,
        expected_count=0
    )

    assert len(remaining_runners) == 0
```

### B. Resource vs Data Guidelines

#### Use **Constants** for:

```python
# Static configuration data
RUNNER_CONFIG = {"cpu": 2, "memory": "4GB"}
WORKFLOW_TIMEOUTS = {"spawn": 600, "cleanup": 300}
WORKFLOW_FILES = {
    "dispatch_test": "workflow_dispatch_test.yaml",
    "crash_test": "workflow_dispatch_crash_test.yaml"
}

# Test data that doesn't change
TEST_LABELS = {"x64", "linux"}
DEFAULT_RECONCILE_INTERVAL = 2
MAX_RUNNERS = 5
```

#### Use **Fixtures** for:

```python
# Resources that need setup/teardown
@pytest_asyncio.fixture
async def clean_app() -> AsyncIterator[Application]:
    app = await deploy_application()
    yield app
    await cleanup_application(app)

# Dynamic or computed values
@pytest.fixture
def unique_repo_name() -> str:
    return f"test-repo-{uuid.uuid4().hex[:8]}"

# External connections and services
@pytest.fixture
def github_client() -> Github:
    return Github(os.getenv("GITHUB_TOKEN"))

@pytest_asyncio.fixture
async def mongodb_connection() -> AsyncIterator[Connection]:
    conn = await create_mongodb_connection()
    yield conn
    await conn.close()
```

### C. Improved Test Naming Examples

#### Better Names by Feature:

```python
# ❌ Overly verbose names
async def test_runner_spawns_successfully_when_configured():
async def test_runner_cleanup_on_scale_down_operation():
async def test_workflow_execution_completes_successfully():
async def test_reactive_mode_spawns_runner_for_queued_job():

# ✅ Clear, concise names focusing on behavior
async def test_runner_spawns():
async def test_runner_cleanup():
async def test_workflow_completes():
async def test_reactive_spawns_runner():

# Runner lifecycle tests
async def test_runner_spawns():
async def test_runner_cleanup():
async def test_runner_scaling():
async def test_runner_registration():

# Workflow execution tests
async def test_workflow_succeeds():
async def test_workflow_fails():
async def test_workflow_timeout():
async def test_workflow_cancellation():

# Configuration management tests
async def test_config_updates():
async def test_config_validation():
async def test_config_rollback():

# Reactive mode tests
async def test_reactive_spawns_runner():
async def test_reactive_processes_queue():
async def test_reactive_scales_down():
```

#### When to Include Context:

```python
# ✅ Add context for edge cases
async def test_runner_spawns_max_capacity():
async def test_workflow_timeout_long_running():
async def test_reactive_cleanup_with_active_jobs():

# ✅ Distinguish similar tests
async def test_config_updates_reconcile_interval():
async def test_config_updates_runner_labels():
```

### D. Module-Level Fixture Organization

#### Create Focused Fixture Modules:

```python
# tests/integration/fixtures/applications.py
"""Application-related fixtures for integration tests."""

import pytest
import pytest_asyncio
from typing import AsyncIterator
from juju.application import Application
from juju.model import Model

@pytest_asyncio.fixture(scope="session")
async def base_model(ops_test) -> Model:
    """Base Juju model for all tests."""
    return ops_test.model

@pytest_asyncio.fixture(scope="function")
async def clean_app(base_model: Model) -> AsyncIterator[Application]:
    """
    Provide a clean application instance with guaranteed cleanup.

    Ensures the application starts and ends with no active runners.
    """
    app = await deploy_github_runner_app(base_model)

    # Ensure clean state
    await app.set_config({"base-virtual-machines": "0"})
    await wait_for_application_ready(app)

    yield app

    # Guaranteed cleanup
    try:
        await cleanup_application_completely(app)
    except Exception as e:
        logger.warning(f"Cleanup failed for {app.name}: {e}")

@pytest_asyncio.fixture(scope="function")
async def app_with_runner(clean_app: Application) -> AsyncIterator[Application]:
    """
    Provide an application with exactly one active runner.

    The runner is guaranteed to be online and ready for work.
    """
    await clean_app.set_config({"base-virtual-machines": "1"})
    await wait_for_runner_count(clean_app, expected_count=1)

    yield clean_app

    # Runner cleanup handled by clean_app fixture
```

```python
# tests/integration/fixtures/github.py
"""GitHub-related fixtures for integration tests."""

import pytest
import pytest_asyncio
from typing import AsyncIterator
from github import Github
from github.Repository import Repository

@pytest_asyncio.fixture(scope="session")
async def github_client(github_token: str) -> Github:
    """GitHub client for API operations."""
    return Github(github_token)

@pytest_asyncio.fixture(scope="function")
async def test_repository(github_client: Github) -> AsyncIterator[Repository]:
    """
    Create a temporary test repository for integration tests.

    Repository is automatically cleaned up after the test.
    """
    repo_name = f"test-repo-{generate_unique_id()}"
    repo = await create_test_repository(github_client, repo_name)

    yield repo

    # Automatic cleanup
    try:
        await cleanup_test_repository(repo)
    except Exception as e:
        logger.warning(f"Failed to cleanup repository {repo_name}: {e}")
```

### E. Complete Test File Structure Example

```python
# tests/integration/test_runner_lifecycle.py
"""Integration tests for GitHub runner lifecycle management."""

import pytest
import pytest_asyncio
from typing import AsyncIterator
from juju.application import Application
from github.Repository import Repository

from tests.integration.helpers.juju_utils import wait_for_runner_count
from tests.integration.helpers.github_utils import verify_runner_registration

# Module-level constants for static data
LIFECYCLE_CONFIG = {
    "reconcile-interval": "1",  # Fast reconcile for testing
    "base-virtual-machines": "0"
}

RUNNER_HARDWARE_CONFIG = {
    "cpu": 2,
    "memory": "4GB",
    "disk": "20GB"
}

TIMEOUT_RUNNER_SPAWN = 600  # 10 minutes
TIMEOUT_CLEANUP = 300       # 5 minutes
TIMEOUT_SCALING = 900       # 15 minutes

# Module-level fixtures for resources needing setup/teardown
@pytest_asyncio.fixture(scope="function")
async def lifecycle_app(clean_app: Application) -> AsyncIterator[Application]:
    """Application configured for lifecycle testing."""
    await clean_app.set_config(LIFECYCLE_CONFIG)
    await wait_for_application_ready(clean_app)
    yield clean_app

# Test functions with improved naming
async def test_runner_spawns(
    lifecycle_app: Application,
    test_repository: Repository
) -> None:
    """
    Test that a runner spawns when requested.

    Given: An application with no active runners
    When: Setting base-virtual-machines to 1
    Then: Exactly one runner should spawn and register with GitHub
    """
    await lifecycle_app.set_config({"base-virtual-machines": "1"})

    await wait_for_runner_count(
        lifecycle_app,
        expected_count=1,
        timeout=TIMEOUT_RUNNER_SPAWN
    )

    registered_runners = await verify_runner_registration(
        test_repository,
        expected_count=1
    )

    assert len(registered_runners) == 1
    assert registered_runners[0].status == "online"

async def test_runner_cleanup(
    lifecycle_app: Application,
    test_repository: Repository
) -> None:
    """
    Test that runners are cleaned up when scaling down.

    Given: An application with one active runner
    When: Setting base-virtual-machines to 0
    Then: The runner should be removed from both Juju and GitHub
    """
    # Start with one runner
    await lifecycle_app.set_config({"base-virtual-machines": "1"})
    await wait_for_runner_count(lifecycle_app, expected_count=1)

    # Scale down to zero
    await lifecycle_app.set_config({"base-virtual-machines": "0"})

    await wait_for_runner_count(
        lifecycle_app,
        expected_count=0,
        timeout=TIMEOUT_CLEANUP
    )

    # Verify GitHub cleanup
    remaining_runners = await verify_runner_registration(
        test_repository,
        expected_count=0
    )

    assert len(remaining_runners) == 0

async def test_runner_scaling(
    lifecycle_app: Application,
    test_repository: Repository
) -> None:
    """
    Test scaling runners up and down multiple times.

    Given: An application with no active runners
    When: Scaling up to 2, then down to 1, then to 0
    Then: Runner counts should match at each step
    """
    scale_sequence = [2, 1, 0]

    for target_count in scale_sequence:
        await lifecycle_app.set_config({
            "base-virtual-machines": str(target_count)
        })

        await wait_for_runner_count(
            lifecycle_app,
            expected_count=target_count,
            timeout=TIMEOUT_SCALING
        )

        # Verify GitHub registration matches
        github_runners = await verify_runner_registration(
            test_repository,
            expected_count=target_count
        )

        assert len(github_runners) == target_count

# Module-level utility functions (not tests)
async def wait_for_application_ready(
    app: Application,
    timeout: int = 1200
) -> None:
    """Wait for application to reach ready state."""
    # Implementation
    pass

def generate_unique_id() -> str:
    """Generate unique identifier for test resources."""
    import uuid
    return uuid.uuid4().hex[:8]
```

## Specific Refactoring Tasks

### 1. Refactor Each Test File

For each file in `tests/integration/test_*.py`:

- **Convert classes to functions**: Remove `class Test*:` and convert methods to functions
- **Extract static data to constants**: Move configuration, timeouts, and test data to module-level constants
- **Use fixtures only for resources**: Things that need setup/teardown, not static data
- **Improve test names**: Remove verbose words, focus on behavior being tested
- **Add proper type hints**: All functions should have complete type annotations

### 2. Update Conftest.py

```python
# tests/integration/conftest.py
"""Main conftest for integration tests - import fixtures from specialized modules."""

# Import all fixtures from specialized modules
from tests.integration.fixtures.applications import *
from tests.integration.fixtures.github import *
from tests.integration.fixtures.openstack import *
from tests.integration.fixtures.mongodb import *

# Keep only the most basic, cross-cutting fixtures here
@pytest.fixture(scope="session")
def test_session_id() -> str:
    """Unique identifier for this test session."""
    import time
    return f"test-session-{int(time.time())}"
```

### 3. Create Specialized Fixture Modules

- **`fixtures/applications.py`**: Juju application fixtures (clean_app, app_with_runner, etc.)
- **`fixtures/github.py`**: GitHub API and repository fixtures (github_client, test_repository, etc.)
- **`fixtures/openstack.py`**: OpenStack resource fixtures (openstack_connection, instance_helper, etc.)
- **`fixtures/mongodb.py`**: MongoDB and queue fixtures (mongodb_connection, queue_manager, etc.)

### 4. Update Import Statements

- **Remove class imports**: Update all test imports since classes no longer exist
- **Import fixtures explicitly**: Make fixture dependencies clear in imports
- **Import utilities**: Import helper functions explicitly
- **Import constants**: Import configuration constants where needed

### 5. Maintain Test Functionality

- **Preserve all test logic**: Ensure no test functionality is lost in refactoring
- **Keep test isolation**: Each test should be independent and not affect others
- **Maintain fixture scoping**: Use appropriate scopes for performance and isolation
- **Improve error messages**: Use constants in assertions for clearer failure messages

## Expected Benefits

### Improved Maintainability

- **Clearer test structure**: Each test is a standalone function with clear purpose
- **Better resource management**: Constants for data, fixtures for resources
- **Easier debugging**: Simpler call stack without class inheritance
- **Cleaner naming**: Concise, behavior-focused test names

### Better Performance

- **Optimal fixture scoping**: Expensive setup operations can be shared appropriately
- **Reduced overhead**: No class instantiation overhead, no fixture overhead for static data
- **Parallel execution**: Functional tests often parallelize better

### Enhanced Readability

- **Linear test flow**: Easy to follow test execution from top to bottom
- **Clear dependencies**: Fixture dependencies are explicit in function signatures
- **Self-documenting**: Function names and constants clearly explain test purpose
- **Visible configuration**: Constants are immediately visible in the module

## Implementation Strategy: Small Incremental PRs

### PR Structure Requirements

- **Small, focused changes**: Each PR should contain 1-3 related files maximum
- **Incremental approach**: Build on previous PRs, don't break existing functionality
- **Self-contained**: Each PR should be independently reviewable and testable
- **Clear titles**: Use descriptive PR titles that explain the specific change

### Suggested PR Sequence

#### Phase 1: Foundation Setup (PRs 1-3)

**PR 1: Create fixture module structure**

- Create `tests/integration/fixtures/` directory
- Create empty `__init__.py`, `applications.py`, `github.py`, `openstack.py`, `mongodb.py`
- Add basic imports and module docstrings
- **Files changed**: ~5 new files
- **Risk**: Low - no existing functionality changed

**PR 2: Extract application fixtures**

- Move application-related fixtures from `conftest.py` to `fixtures/applications.py`
- Update imports in `conftest.py`
- Ensure all tests still pass
- **Files changed**: `conftest.py`, `fixtures/applications.py`
- **Risk**: Medium - fixture reorganization

**PR 3: Extract GitHub and external service fixtures**

- Move GitHub, OpenStack, MongoDB fixtures to respective modules
- Update remaining imports in `conftest.py`
- **Files changed**: `conftest.py`, `fixtures/github.py`, `fixtures/openstack.py`, `fixtures/mongodb.py`
- **Risk**: Medium - fixture reorganization

#### Phase 2: Test File Refactoring (PRs 4-8)

**PR 4: Refactor test_runner_lifecycle.py**

- Convert class-based tests to functions
- Extract constants for static data
- Improve test naming
- **Files changed**: `test_runner_lifecycle.py`
- **Risk**: Medium - test structure change

**PR 5: Refactor test_reactive.py**

- Convert class-based tests to functions
- Extract constants and improve naming
- **Files changed**: `test_reactive.py`
- **Risk**: Medium - test structure change

**PR 6: Refactor test*workflow*\*.py files**

- Convert workflow-related test classes to functions
- Extract workflow constants
- **Files changed**: 2-3 workflow test files
- **Risk**: Medium - test structure change

**PR 7: Refactor test*charm*\*.py files**

- Convert charm-related test classes to functions
- Extract charm configuration constants
- **Files changed**: 2-3 charm test files
- **Risk**: Medium - test structure change

**PR 8: Refactor remaining test files**

- Convert any remaining class-based tests
- Extract remaining constants
- **Files changed**: Remaining test files
- **Risk**: Low-Medium - final cleanup

#### Phase 3: Cleanup and Optimization (PRs 9-10)

**PR 9: Remove unused imports and dead code**

- Clean up unused imports across all files
- Remove any dead code or commented-out sections
- **Files changed**: Multiple test files
- **Risk**: Low - cleanup only

**PR 10: Documentation and final polish**

- Update test documentation
- Add type hints where missing
- Final naming improvements
- **Files changed**: Multiple files, documentation
- **Risk**: Low - polish only

### PR Guidelines

#### Each PR Must Include:

1. **Clear description**: Explain what is being refactored and why
2. **Test verification**: Confirm all tests still pass
3. **Backward compatibility**: Ensure no functionality is lost
4. **Focused scope**: Don't mix different types of changes

#### PR Template Example:

```markdown
## Refactor: Convert test_runner_lifecycle.py to functional tests

### Changes Made

- Converted `TestRunnerLifecycle` class to standalone functions
- Extracted static configuration to module-level constants
- Improved test naming: `test_runner_cleanup_on_scale_down` → `test_runner_cleanup`
- Added proper type hints to all functions

### Constants Added

- `LIFECYCLE_CONFIG`: Basic application configuration
- `TIMEOUT_RUNNER_SPAWN`: Runner spawn timeout
- `TIMEOUT_CLEANUP`: Cleanup operation timeout

### Test Verification

- [ ] All tests in `test_runner_lifecycle.py` pass
- [ ] No other test files affected
- [ ] Test functionality preserved

### Files Changed

- `tests/integration/test_runner_lifecycle.py`
```

#### Before Each PR:

1. **Run affected tests**: Ensure changes don't break functionality
2. **Check dependencies**: Verify no other files are affected
3. **Review scope**: Confirm PR contains only related changes
4. **Test isolation**: Ensure tests remain independent

#### PR Review Checklist:

- [ ] All existing test functionality preserved
- [ ] Code follows established patterns from previous PRs
- [ ] Type hints added to new/modified functions
- [ ] Constants used instead of magic numbers/strings
- [ ] Test names are concise and behavior-focused
- [ ] No nested functions introduced
- [ ] Proper fixture scoping maintained

## Implementation Order

### Implementation Order (Incremental Approach)

1. **Phase 1 - Foundation (PRs 1-3)**: Create fixture modules and reorganize existing fixtures
2. **Phase 2 - Test Refactoring (PRs 4-8)**: Convert test files one at a time to functional approach
3. **Phase 3 - Cleanup (PRs 9-10)**: Final cleanup, optimization, and documentation

## Quality Standards

- **No nested functions**: All functions must be at module level
- **Constants over fixtures**: Use constants for static data, fixtures only for resources
- **Concise naming**: Test names should be clear but not verbose
- **Type hints everywhere**: All functions and fixtures must have type annotations
- **Comprehensive docstrings**: Document all public functions and their behavior
- **Proper cleanup**: All fixtures must handle cleanup gracefully
- **Test isolation**: Each test must be independent and not affect others
- **Incremental delivery**: Each PR must be small, focused, and independently valuable

## Success Criteria

### Per PR:

- All existing tests continue to pass
- No regression in test functionality
- Code quality improvements are measurable
- Changes are focused and reviewable (< 500 lines changed)

### Overall Project:

- 100% of class-based tests converted to functional tests
- All static data moved to constants
- All test names follow new naming conventions
- Fixture organization improved and modularized
- Test execution time maintained or improved
- Code maintainability significantly enhanced

Please implement this refactoring using the incremental PR approach, ensuring each change is small, focused, and builds upon the previous work. This approach will make the refactoring safer, more reviewable, and easier to rollback if issues arise.
