# Security Audit Command

## Overview
The `audit` command orchestrates a comprehensive security assessment across four phases, producing a detailed report of vulnerabilities and misconfigurations.

## Command Invocation
```bash
jarvis security-audit audit [--target=<path>] [--format=json|markdown] [--severity=critical,high]
```

## Phase 1: Dependency Scanning

### Step 1.1: Detect Package Manager
- Determine project type by examining: `package.json`, `pyproject.toml`, `Gemfile`, `pom.xml`, `go.mod`
- For each detected package manager, proceed with corresponding audit

### Step 1.2: Run Language-Specific Audits

#### Node.js Projects (npm)
```bash
npm audit --json > audit-results.json
```
- Parse severity levels (critical, high, moderate, low)
- Extract package name, current version, vulnerable range, and CVE numbers
- Log all findings with severity >= user threshold

#### Python Projects (pip)
```bash
pip audit --desc
```
- Capture all vulnerable packages
- Note available patches/versions
- Cross-reference with CVE database

#### Ruby Projects (bundler)
```bash
bundle audit check --update
```

#### Java/Maven Projects
```bash
mvn dependency-check:check
```

### Step 1.3: Parse and Prioritize Results
- Filter by severity level (default: critical + high)
- For each vulnerability:
  - **Vulnerability ID** (CVE-XXXX-XXXXX or advisory ID)
  - **Package Name** and affected version range
  - **Patch Available** (yes/no and version)
  - **Public Exploit** (yes/no)
  - **CVSS Score** (if available)

---

## Phase 2: Static Code Analysis

### Step 2.1: Search for Hardcoded Secrets
Use bash/grep patterns to identify:
- Database connection strings in code
- AWS access keys, API keys, JWT tokens
- Private keys (RSA, PEM files)
- OAuth secrets and Bearer tokens

```bash
# Common patterns to search for
grep -r "password\s*=\s*['\"]" src/
grep -r "api[_-]?key\s*=\s*['\"]" src/
grep -r "secret\s*=\s*['\"]" src/
grep -r "BEGIN\s*RSA\s*PRIVATE\s*KEY" .
```

### Step 2.2: Analyze Authentication & Middleware
- Review files in `src/auth/`, `src/middleware/`, `src/services/` folders
- Check for:
  - Weak password hashing (MD5, SHA1)
  - Missing input validation
  - Insufficient rate limiting
  - Unvalidated redirects
  - CORS misconfiguration

### Step 2.3: Search for Injection Vectors
Identify potential:
- **SQL Injection**: String concatenation in database queries
- **Command Injection**: `exec()`, `system()`, shell interpolation
- **Path Traversal**: Unsanitized file path operations
- **Template Injection**: Unsafe template rendering

### Step 2.4: Cryptography Review
Look for:
- Deprecated algorithms (MD5, SHA1, DES)
- Hardcoded cryptographic keys
- Insufficient key lengths
- Missing initialization vectors (IVs)
- Weak random number generation

---

## Phase 3: Configuration Audit

### Step 3.1: Environment Variable Handling
- Verify `.env` files are in `.gitignore`
- Check that secrets are not logged
- Validate all required secrets are documented in `.env.example`
- Ensure no secrets committed to git history

### Step 3.2: Security Headers & CORS
- Review server configuration for:
  - Content-Security-Policy (CSP)
  - X-Frame-Options
  - X-Content-Type-Options
  - Strict-Transport-Security (HSTS)
  - CORS headers restrictiveness

### Step 3.3: Database Security
- Check for:
  - Unencrypted connections
  - Default credentials
  - Missing authentication
  - Exposed database ports

### Step 3.4: API Security
- Review:
  - API authentication (API keys, OAuth, mTLS)
  - Rate limiting
  - Input validation
  - Output encoding

---

## Phase 4: Validation & Reporting

### Step 4.1: Verify Findings
For each identified vulnerability:
1. Cross-check with current CVE database via web search
2. Confirm patch availability and version
3. Document exploit availability (PoC, public tools)
4. Add CVSS score and base metrics

### Step 4.2: Compile Report
- Use `templates/report.md` as the base template
- Populate with findings from phases 1-3
- Group by severity and vulnerability type
- Include remediation guidance

### Step 4.3: Output Formats
- **Markdown** (default): Human-readable report with formatting
- **JSON**: Machine-parseable results for CI/CD integration

---

## Constraint Enforcement

### During Execution:
1. ✅ Only execute binaries explicitly listed in `manifest.yaml:allowed_tools`
2. ✅ Never upload full source code—use local analysis and targeted searches
3. ✅ Every finding includes "Path to Exploit" and "Recommended Fix"
4. ✅ Document all assumptions (e.g., "Assumes packages are up-to-date in lock file")

### Reporting:
1. ✅ Include severity justification
2. ✅ Provide remediation priority
3. ✅ Link to official CVE and advisory documentation
4. ✅ Exclude speculative or unverified findings

---

## Example Output

### Finding (Phase 1 - Dependency):
```
[CRITICAL] CVE-2023-39611 in express < 4.19.0
  Package: express
  Affected Versions: < 4.19.0
  Current Version: 4.18.2
  Patch Available: Yes (4.19.0+)
  Path to Exploit: Prototype pollution attack via malformed Content-Type headers
  Recommended Fix: npm install express@^4.19.0
  References: https://nvd.nist.gov/vuln/detail/CVE-2023-39611
```

### Finding (Phase 2 - Static Analysis):
```
[HIGH] Hardcoded API Key in src/services/stripe.js:42
  Vulnerability Type: Exposed Secret
  Location: src/services/stripe.js, line 42
  Code: const stripeKey = "sk_live_abc123xyz..."
  Path to Exploit: Attacker can use exposed key to access Stripe account
  Recommended Fix: Move to environment variable: const stripeKey = process.env.STRIPE_SECRET_KEY
```

---

## Execution Summary
The audit command completes with:
- **Total Findings**: X (Critical: Y, High: Z, etc.)
- **Actionable Items**: Prioritized remediation list
- **Report File**: Path to generated report
- **Estimated Remediation Time**: Based on complexity
