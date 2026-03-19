---
description: Process brain dumps into structured CTO notes. Categorizes thoughts, asks clarifying questions, and updates the right files.
argument-hint: "Your unstructured thoughts, bullet points, or brain dump"
---

# CTO Think - Brain Dump Processor

You are processing a brain dump of thoughts and categorizing them into structured CTO notes.

## User Input

$ARGUMENTS

## Context

- Current date: !`date +%Y-%m-%d`
- Current quarter: (Calculate from date: Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec)

### Existing Notes
!`ls -la .notes/ 2>/dev/null || echo "No .notes folder yet"`

### Current Priorities (if exists)
!`head -50 .notes/priorities.md 2>/dev/null || echo "No priorities.md yet"`

### Current Technical Debt (if exists)
!`head -30 .notes/technical-debt.md 2>/dev/null || echo "No technical-debt.md yet"`

## Your Task

### Step 1: Parse & Categorize

For each thought/bullet point provided, categorize it into ONE of:

| Category | Target File | Examples |
|----------|-------------|----------|
| **Priority** | `.notes/priorities.md` | "Focus on mobile app", "Ship feature X first" |
| **Technical Debt** | `.notes/technical-debt.md` | "Refactor auth service", "Fix N+1 queries" |
| **Architecture Decision** | `.notes/architecture-decisions.md` | "Use MCP for agents", "Switch to PostgreSQL" |
| **Business Metric** | `.notes/business-metrics.md` | "Track MAU", "Monitor churn rate" |
| **Testing** | `.notes/testing-roadmap.md` | "Add integration tests", "Coverage goal 70%" |
| **Quarterly Planning** | `.notes/quarterly-plan.md` | "Q1 focus: mobile", "Hire 2 engineers" |

### Step 2: Ask Clarifying Questions

For each categorized item, ask specific questions to fill in details:

**For Priorities:**
- What's the business impact?
- What's the estimated effort (Small/Medium/Large)?
- Who owns this?
- What's the deadline?
- What are the dependencies?

**For Technical Debt:**
- What's the impact score (Critical/High/Medium/Low)?
- What file(s) does this affect?
- What's the effort to fix?

**For Architecture Decisions:**
- What problem does this solve?
- What alternatives were considered?
- What are the tradeoffs?

**For Metrics:**
- What's the current value?
- What's the target value?
- How will this be measured?

**For Testing:**
- Which files/services need tests?
- What's the priority level?
- Are there any blockers?

### Step 3: Present Change Plan

Show the user:

```
## Categorized Items

### Priorities (X items)
- [Item] → Will add to priorities.md as [Critical/High/Medium/Low]

### Technical Debt (X items)
- [Item] → Will add to technical-debt.md with ROI score [X]

### Architecture Decisions (X items)
- [Item] → Will create ADR-XXX in architecture-decisions.md

### [Other categories...]

## Questions Before Proceeding

1. [Question about item 1]
2. [Question about item 2]
...

## Proposed Changes

I'll update the following files:
- `.notes/priorities.md` - Add X items
- `.notes/technical-debt.md` - Add X items
- [etc.]

Ready to proceed? (yes/no)
```

### Step 4: Execute Changes

Only after user confirmation:

1. Create `.notes/` folder if it doesn't exist
2. Read existing note files (to preserve content)
3. Append new items to appropriate sections
4. Update `.notes/00-README.md` with change summary

## Error Handling

| Situation | Response |
|-----------|----------|
| No bullet points provided | Ask: "What thoughts would you like to process? List them as bullets" |
| Ambiguous categorization | Ask: "Is '[point]' about priorities, debt, a decision, or something else?" |
| User skips questions | Mark fields as "TBD" and note assumptions |
| `.notes/` doesn't exist | Create it with the first note |

## Output Format

Be concise but thorough. Use tables for categorization. Ask all questions upfront rather than one at a time.
