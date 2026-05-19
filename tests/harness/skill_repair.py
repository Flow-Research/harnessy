#!/usr/bin/env python3
"""
Skill Repair via LLM (Multi-provider)

This module implements LLM-based skill repair for the autoresearch loop.
Given a broken skill and failure context, it uses an LLM to:
1. Analyze what went wrong
2. Propose specific fixes to SKILL.md
3. Apply those fixes
4. Record the improvement

Supported LLM providers:
- google-genai (Gemini) — FREE tier available
- anthropic (Claude) — Paid
- openai (GPT) — Paid but has free trial credits

Usage:
    python3 skill_repair.py --skill <name> --broken-skill-path <path> --test-log <path> \
        [--provider gemini|claude|gpt] [--auto-apply]
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Any


class SkillRepair:
    """LLM-based skill repair supporting multiple providers."""

    def __init__(self, provider: str = "gemini", api_key: Optional[str] = None, model: Optional[str] = None):
        """Initialize the skill repair module.
        
        Args:
            provider: "gemini" (default, free), "claude", or "gpt"
            api_key: API key (defaults to env var based on provider)
            model: Model name (auto-selected if not provided)
        """
        self.provider = provider.lower()
        
        if self.provider == "gemini":
            self._init_gemini(api_key, model)
        elif self.provider == "claude":
            self._init_claude(api_key, model)
        elif self.provider == "gpt":
            self._init_gpt(api_key, model)
        else:
            raise ValueError(f"Unsupported provider: {provider}. Choose: gemini, claude, gpt")
    
    def _init_gemini(self, api_key: Optional[str], model: Optional[str]):
        """Initialize Google Gemini (free tier available)."""
        try:
            from google import genai
        except ImportError:
            raise RuntimeError(
                "google-genai not installed. Run: pip install google-genai"
            )
        
        api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "No API key provided. Set GOOGLE_API_KEY or pass --api-key. "
                "Get free key at: https://aistudio.google.com/app/apikey"
            )
        
        self.client = genai.Client(api_key=api_key)
        self.model = model or "gemini-2.0-flash"
    
    def _init_claude(self, api_key: Optional[str], model: Optional[str]):
        """Initialize Anthropic Claude (paid)."""
        try:
            from anthropic import Anthropic
        except ImportError:
            raise RuntimeError(
                "anthropic not installed. Run: pip install anthropic"
            )
        
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("No API key provided. Set ANTHROPIC_API_KEY or pass --api-key")
        
        self.client = Anthropic(api_key=api_key)
        self.model = model or "claude-opus-4-1-20250805"
    
    def _init_gpt(self, api_key: Optional[str], model: Optional[str]):
        """Initialize OpenAI GPT (paid, but free trial credits available)."""
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError(
                "openai not installed. Run: pip install openai"
            )
        
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("No API key provided. Set OPENAI_API_KEY or pass --api-key")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model or "gpt-4o-mini"

    def analyze_failure(
        self,
        skill_name: str,
        broken_skill_content: str,
        test_log: str,
        baseline_skill_content: Optional[str] = None,
    ) -> dict:
        """Analyze what went wrong with the skill.
        
        Args:
            skill_name: Name of the skill
            broken_skill_content: Current (broken) SKILL.md content
            test_log: Output from failed test run
            baseline_skill_content: Original (working) SKILL.md content
            
        Returns:
            dict with 'analysis' and 'proposals' keys
        """
        print(f"🔍 Analyzing failure for skill: {skill_name} (using {self.provider})", file=sys.stderr)
        
        # Build comparison context
        comparison = ""
        if baseline_skill_content:
            baseline_lines = baseline_skill_content.split("\n")
            broken_lines = broken_skill_content.split("\n")
            
            changes = []
            for i, (b, br) in enumerate(zip(baseline_lines, broken_lines)):
                if b != br:
                    changes.append(f"Line {i+1}: '{b[:50]}...' → '{br[:50]}...'")
            
            if changes:
                comparison = "\n**Changes detected:**\n" + "\n".join(changes[:10])
        
        prompt = f"""You are an expert skill repair agent for Harnessy.

A skill has been intentionally broken (entropy injection) and we need to fix it.

**Skill Name:** {skill_name}

**Current (Broken) SKILL.md:**
```markdown
{broken_skill_content[:2000]}
```

**Test Failure Log (first 1500 chars):**
```
{test_log[:1500]}
```

{comparison}

**Your Task:**
1. Analyze what went wrong based on the test failures
2. Identify the injected failure(s) - is it:
   - Missing critical steps or sections?
   - Corrupted instructions or logic?
   - Incomplete documentation?
3. Propose specific, minimal fixes to restore the skill
4. For each fix, provide:
   - The problematic section
   - The exact replacement text
   - Why it fixes the issue

**Output Format:**
Return ONLY a JSON object (no markdown, no code blocks):
{{
  "failure_type": "missing-step | corrupted-logic | incomplete-doc",
  "analysis": "2-3 sentence explanation",
  "proposals": [
    {{
      "section": "section name",
      "old_text": "exact text to replace (3-5 lines)",
      "new_text": "exact replacement text",
      "rationale": "why this fixes the issue"
    }}
  ]
}}

Be precise. The old_text must match exactly."""

        try:
            if self.provider == "gemini":
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt
                )
                response_text = response.text
            elif self.provider == "claude":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = response.content[0].text
            elif self.provider == "gpt":
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = response.choices[0].message.content
        except Exception as e:
            print(f"✗ LLM API error: {e}", file=sys.stderr)
            return {
                "failure_type": "unknown",
                "analysis": f"LLM error: {str(e)}",
                "proposals": []
            }
        
        # Parse JSON response
        try:
            json_str = response_text.strip()
            # Remove markdown code blocks if present
            if json_str.startswith("```"):
                json_match = re.search(r'```(?:json)?\n?(.*?)\n?```', json_str, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
            
            result = json.loads(json_str)
            print(f"✓ Analysis complete: {result.get('failure_type', 'unknown')}", file=sys.stderr)
            return result
        except (json.JSONDecodeError, AttributeError) as e:
            print(f"⚠ Failed to parse LLM response: {e}", file=sys.stderr)
            print(f"Response was: {response_text[:500]}", file=sys.stderr)
            return {
                "failure_type": "unknown",
                "analysis": "Could not parse LLM response",
                "proposals": []
            }

    def apply_repairs(
        self,
        skill_path: str,
        proposals: list[dict],
        dry_run: bool = False,
    ) -> tuple[bool, list[dict]]:
        """Apply proposed repairs to the skill file.
        
        Args:
            skill_path: Path to SKILL.md file
            proposals: List of repair proposals from analyze_failure()
            dry_run: If True, don't actually modify files
            
        Returns:
            (success: bool, applied_repairs: list[dict])
        """
        skill_file = Path(skill_path)
        if not skill_file.exists():
            print(f"✗ Skill file not found: {skill_path}", file=sys.stderr)
            return False, []
        
        content = skill_file.read_text()
        original_content = content
        applied = []
        
        for i, proposal in enumerate(proposals):
            old_text = proposal.get("old_text", "")
            new_text = proposal.get("new_text", "")
            section = proposal.get("section", "unknown")
            
            if not old_text or not new_text:
                print(f"⚠ Proposal {i+1}: missing old_text or new_text, skipping", file=sys.stderr)
                continue
            
            if old_text not in content:
                print(f"⚠ Proposal {i+1}: old_text not found in skill, skipping", file=sys.stderr)
                continue
            
            # Apply the fix
            content = content.replace(old_text, new_text, 1)
            applied.append({
                "section": section,
                "type": proposal.get("type", "edit"),
                "success": True,
            })
            print(f"✓ Applied repair {i+1}: {section}", file=sys.stderr)
        
        if not applied:
            print("✗ No repairs could be applied", file=sys.stderr)
            return False, []
        
        if dry_run:
            print(f"[DRY RUN] Would have modified {skill_path}", file=sys.stderr)
            return True, applied
        
        # Write the repaired skill
        skill_file.write_text(content)
        print(f"✓ Skill repaired and written to {skill_path}", file=sys.stderr)
        
        # Bump version in manifest.yaml if it exists
        manifest_path = skill_file.parent / "manifest.yaml"
        if manifest_path.exists():
            manifest = manifest_path.read_text()
            # Simple version bump: 0.X.Y -> 0.X.(Y+1)
            version_match = re.search(r'version: (\d+\.\d+\.\d+)', manifest)
            if version_match:
                old_version = version_match.group(1)
                parts = old_version.split(".")
                parts[2] = str(int(parts[2]) + 1)
                new_version = ".".join(parts)
                manifest = manifest.replace(f"version: {old_version}", f"version: {new_version}")
                manifest_path.write_text(manifest)
                print(f"✓ Bumped version: {old_version} → {new_version}", file=sys.stderr)
        
        return True, applied

    def record_improvement(
        self,
        skill_name: str,
        skill_path: str,
        proposals: list[dict],
        failure_type: str,
    ) -> bool:
        """Record the improvement in traces.
        
        Args:
            skill_name: Skill being improved
            skill_path: Path to skill directory
            proposals: Applied proposals
            failure_type: Type of failure that was fixed
            
        Returns:
            True if recorded successfully
        """
        traces_root = Path.home() / ".agents" / "traces" / skill_name
        traces_root.mkdir(parents=True, exist_ok=True)
        
        improvements_file = traces_root / "improvements.ndjson"
        
        improvement_record = {
            "improvement_id": f"imp_{datetime.now().strftime('%Y%m%d')}_{len(list(traces_root.glob('*')))}",
            "timestamp": datetime.now().isoformat(),
            "skill": skill_name,
            "method": "llm-repair",
            "failure_type": failure_type,
            "proposals_applied": len(proposals),
            "changes": proposals,
        }
        
        with open(improvements_file, "a") as f:
            f.write(json.dumps(improvement_record) + "\n")
        
        print(f"✓ Recorded improvement: {improvement_record['improvement_id']}", file=sys.stderr)
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Repair a broken skill using an LLM"
    )
    parser.add_argument("--skill", required=True, help="Skill name")
    parser.add_argument("--broken-skill-path", required=True, help="Path to broken SKILL.md")
    parser.add_argument("--baseline-skill-path", help="Path to original (baseline) SKILL.md")
    parser.add_argument("--test-log", required=True, help="Path to test failure log")
    parser.add_argument(
        "--provider",
        choices=["gemini", "claude", "gpt"],
        default="gemini",
        help="LLM provider: gemini (free, default), claude (paid), or gpt (paid)"
    )
    parser.add_argument("--api-key", help="API key (or use env var: GOOGLE_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY)")
    parser.add_argument("--model", help="Model to use (auto-selected if not provided)")
    parser.add_argument("--dry-run", action="store_true", help="Analyze but don't apply repairs")
    parser.add_argument("--auto-apply", action="store_true", help="Apply repairs without confirmation")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    try:
        # Read input files
        broken_content = Path(args.broken_skill_path).read_text()
        test_log_content = Path(args.test_log).read_text()
        baseline_content = None
        if args.baseline_skill_path:
            baseline_content = Path(args.baseline_skill_path).read_text()

        # Initialize repair agent
        repair = SkillRepair(provider=args.provider, api_key=args.api_key, model=args.model)

        # Analyze failure
        analysis = repair.analyze_failure(
            skill_name=args.skill,
            broken_skill_content=broken_content,
            test_log=test_log_content,
            baseline_skill_content=baseline_content,
        )

        if args.json:
            print(json.dumps({"analysis": analysis}, indent=2))
            return 0

        # Apply repairs
        if analysis.get("proposals"):
            print(f"\n📋 Found {len(analysis['proposals'])} repair proposals")
            
            if not args.auto_apply and not args.dry_run:
                response = input("Apply repairs? (y/n): ")
                if response.lower() != "y":
                    print("Repairs cancelled")
                    return 1

            success, applied = repair.apply_repairs(
                skill_path=args.broken_skill_path,
                proposals=analysis["proposals"],
                dry_run=args.dry_run,
            )

            if success:
                repair.record_improvement(
                    skill_name=args.skill,
                    skill_path=str(Path(args.broken_skill_path).parent),
                    proposals=applied,
                    failure_type=analysis.get("failure_type", "unknown"),
                )
                print(f"✓ Skill repair complete: {len(applied)} changes applied")
                return 0
            else:
                print("✗ Repair failed")
                return 1
        else:
            print("✗ No repair proposals generated")
            return 1

    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        if args.json:
            print(json.dumps({"error": str(e)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
