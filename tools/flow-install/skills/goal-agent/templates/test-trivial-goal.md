# Goal: Create a greeting file

## Objective

Create a file called `greeting.txt` in the current directory containing exactly "Hello from goal-agent!"

## Constraints

- Max iterations: 5
- Budget per phase: $1.00
- Total budget: $3.00
- Model: sonnet
- Allowed tools: Bash, Read, Write, Edit

## Verification

### Commands

```bash
cat greeting.txt | grep "Hello from goal-agent!"
```

### File Checks

- [ ] `greeting.txt` exists

## Context

This is a trivial test goal to verify the goal-agent system works end-to-end.
