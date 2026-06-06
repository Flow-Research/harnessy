# Testing Strategy

## Purpose

Harnessy-managed repositories should prefer tests that exercise real system
behavior. Unit tests are useful for pure logic, but product confidence comes
from integration paths that run against real runtimes, real persistence, and
real browser/API boundaries.

## Default Hierarchy

Choose the strongest practical test shape in this order:

1. Full integration tests in a Docker-backed environment.
2. API or service integration tests with Testcontainers-managed dependencies.
3. Browser E2E tests against a real app backend and test database.
4. Narrow unit tests for pure functions, parsers, transforms, and edge cases.
5. Mocks only by documented exception.

Testcontainers is the preferred default for app-level integration tests.
Docker Compose is the fallback when the system is best represented as a
multi-service environment or when a repo already has a reliable compose stack.

## Mock Policy

Mocks are allowed when they isolate a true external boundary or make a rare
failure mode testable. Examples:

- third-party payment, email, SMS, hosting, or AI provider APIs
- time, randomness, network outages, and hard-to-trigger provider errors
- browser APIs that cannot run in the target test environment

Mocks are false-green risks when they replace the code under test:

- database clients or repositories
- auth/session/tenant checks
- internal service-layer methods
- API route handlers called through direct stubs instead of HTTP/request paths
- queue, cache, or storage behavior that can run in a container

When a mock is necessary, the test or profile should document the boundary and
why a container-backed or real integration test is not feasible.

## Container Contract

Repositories should describe integration dependencies in the QA profile under
`.jarvis/context/profiles/qa.json`.

Recommended fields:

```json
{
  "testEnvironment": {
    "runtimePreference": "testcontainers",
    "composeFile": "docker-compose.test.yml",
    "services": ["postgres", "redis"],
    "mockPolicy": {
      "default": "warn",
      "allowedExternalBoundaries": ["stripe", "sendgrid"],
      "exceptions": []
    }
  }
}
```

The profile is not required to provision every environment itself, but it
should make the intended integration runtime discoverable to agents and CI.

## QA Integration

The QA standard remains the source of truth for regression scenarios, DB
assertions, browser walkthroughs, and drift detection. This strategy adds the
test execution preference:

- persistence-sensitive tests should use a real test database or document the
  environment limitation
- browser tests should run against a real app instance when user-visible or
  persisted outcomes matter
- mock-heavy suites should be reported as warning-level false-green risks in v1
- CI should run container-backed integration commands before deploy gates when
  the profile declares them

## Agent Guidance

When adding or reviewing tests, agents should:

- ask whether an integration/container test is practical before writing mocks
- prefer Testcontainers or existing Docker Compose assets for DB/API behavior
- keep pure unit tests narrow and focused
- call out mock exceptions explicitly in summaries and QA reports
- never claim production confidence from mock-only tests when integration
  behavior is in scope
