# Security Audit Report

**Project**: {{PROJECT_NAME}}  
**Scan Date**: {{SCAN_DATE}}  
**Auditor**: Security Audit Skill v1.0  
**Report Format**: {{REPORT_VERSION}}

---

## Executive Summary

| Metric | Count |
|--------|-------|
| **Critical Findings** | {{CRITICAL_COUNT}} |
| **High Severity** | {{HIGH_COUNT}} |
| **Medium Severity** | {{MEDIUM_COUNT}} |
| **Low Severity** | {{LOW_COUNT}} |
| **Total Findings** | {{TOTAL_COUNT}} |
| **Remediable Issues** | {{REMEDIABLE_COUNT}} |
| **Risk Score** | {{RISK_SCORE}} / 100 |

### Overall Assessment
{{OVERALL_ASSESSMENT}}

**Recommended Action**: {{ACTION_PRIORITY}}

---

## Critical Findings

{{#CRITICAL_FINDINGS}}

### Finding: {{FINDING_ID}}
- **Vulnerability Type**: {{VULNERABILITY_TYPE}}
- **Severity**: 🔴 **CRITICAL**
- **CVSS Score**: {{CVSS_SCORE}} ({{CVSS_VECTOR}})
- **Location**: `{{FILE_PATH}}:{{LINE_NUMBER}}`

**Description**:  
{{DESCRIPTION}}

**Path to Exploit**:  
{{EXPLOIT_PATH}}

**Recommended Fix**:  
{{RECOMMENDED_FIX}}

**References**:
- {{REFERENCE_URL_1}}
- {{REFERENCE_URL_2}}

**Time to Fix**: {{ESTIMATED_TIME}}  
**Priority**: {{PRIORITY}}

---

{{/CRITICAL_FINDINGS}}

## High Severity Findings

{{#HIGH_FINDINGS}}

### Finding: {{FINDING_ID}}
- **Vulnerability Type**: {{VULNERABILITY_TYPE}}
- **Severity**: 🟠 **HIGH**
- **CVSS Score**: {{CVSS_SCORE}}
- **Location**: `{{FILE_PATH}}:{{LINE_NUMBER}}`

**Description**:  
{{DESCRIPTION}}

**Path to Exploit**:  
{{EXPLOIT_PATH}}

**Recommended Fix**:  
{{RECOMMENDED_FIX}}

**References**:
- {{REFERENCE_URL}}

**Time to Fix**: {{ESTIMATED_TIME}}

---

{{/HIGH_FINDINGS}}

## Medium Severity Findings

{{#MEDIUM_FINDINGS}}

### Finding: {{FINDING_ID}}
- **Vulnerability Type**: {{VULNERABILITY_TYPE}}
- **Severity**: 🟡 **MEDIUM**
- **Description**: {{DESCRIPTION}}
- **Location**: `{{FILE_PATH}}`
- **Recommendation**: {{RECOMMENDED_FIX}}

---

{{/MEDIUM_FINDINGS}}

## Low Severity & Informational

{{#LOW_FINDINGS}}

### {{FINDING_ID}}: {{DESCRIPTION}}
- **Recommendation**: {{RECOMMENDED_FIX}}

{{/LOW_FINDINGS}}

---

## Vulnerability Breakdown by Category

### Dependency Vulnerabilities
- **Total**: {{DEP_TOTAL}}
- **Critical/High**: {{DEP_CRITICAL_HIGH}}
- **Patch Available**: {{DEP_PATCHABLE}}

**Affected Packages**:
```
{{DEP_LIST}}
```

### Hardcoded Secrets
- **Total**: {{SECRETS_TOTAL}}
- **API Keys**: {{SECRETS_KEYS}}
- **Credentials**: {{SECRETS_CREDENTIALS}}
- **Private Keys**: {{SECRETS_PRIVATE}}

### Code Quality Issues
- **Weak Cryptography**: {{WEAK_CRYPTO_COUNT}}
- **Injection Vectors**: {{INJECTION_COUNT}}
- **Auth/Access Control**: {{AUTH_COUNT}}

### Configuration Issues
- **Missing Headers**: {{HEADER_COUNT}}
- **CORS Misconfigs**: {{CORS_COUNT}}
- **Exposed Secrets**: {{CONFIG_SECRETS_COUNT}}

---

## Remediation Roadmap

### Phase 1: Immediate (Within 24 hours)
{{#PHASE1_ITEMS}}
- [ ] {{FINDING_ID}}: {{ACTION}}
{{/PHASE1_ITEMS}}

### Phase 2: Short-term (Within 1 week)
{{#PHASE2_ITEMS}}
- [ ] {{FINDING_ID}}: {{ACTION}}
{{/PHASE2_ITEMS}}

### Phase 3: Medium-term (Within 1 month)
{{#PHASE3_ITEMS}}
- [ ] {{FINDING_ID}}: {{ACTION}}
{{/PHASE3_ITEMS}}

### Phase 4: Long-term (Hardening)
{{#PHASE4_ITEMS}}
- [ ] {{FINDING_ID}}: {{ACTION}}
{{/PHASE4_ITEMS}}

---

## Compliance & Standards Coverage

| Framework | Coverage | Status |
|-----------|----------|--------|
| **OWASP Top 10** | {{OWASP_COVERAGE}}% | {{OWASP_STATUS}} |
| **CWE Top 25** | {{CWE_COVERAGE}}% | {{CWE_STATUS}} |
| **GDPR** | {{GDPR_COVERAGE}}% | {{GDPR_STATUS}} |
| **SOC 2** | {{SOC2_COVERAGE}}% | {{SOC2_STATUS}} |

---

## Assumptions & Scope

### In Scope
- ✅ Public source code in the repository
- ✅ Dependency manifest files (`package.json`, `pyproject.toml`, etc.)
- ✅ Configuration files (checked against defaults)
- ✅ Known CVE databases (NVD, GitHub Security Advisories)

### Out of Scope
- ❌ Runtime behavior analysis (requires dynamic testing)
- ❌ Compiled binaries (bytecode analysis not included)
- ❌ Penetration testing or active exploitation
- ❌ Third-party SaaS integrations requiring special access
- ❌ Private/internal vulnerability databases

### Known Limitations
{{LIMITATIONS}}

---

## Next Steps

1. **Review Findings**: Share this report with your development team
2. **Prioritize Fixes**: Focus on Critical/High severity items in Phase 1
3. **Implement Fixes**: Use the "Recommended Fix" section for each finding
4. **Re-audit**: Run the audit again after applying fixes to verify resolution
5. **Establish Practices**:
   - Enable `npm audit` or equivalent in CI/CD pipeline
   - Set up dependency update automation (Dependabot, Renovate)
   - Implement pre-commit hooks for secret scanning
   - Schedule regular security audits (monthly or quarterly)

---

## Questions or Clarifications?

For more information about specific vulnerabilities:
- **CVE Details**: Search the National Vulnerability Database (NVD) at https://nvd.nist.gov/
- **OWASP**: Visit https://owasp.org/www-project-top-ten/ for vulnerability guidance
- **Package Security**: Check package advisories on npm, PyPI, or your language's registry

---

**Report Generated**: {{SCAN_DATE}} at {{SCAN_TIME}} UTC  
**Audit Skill Version**: 1.0  
**Harnessy Framework Version**: {{HARNESSY_VERSION}}
