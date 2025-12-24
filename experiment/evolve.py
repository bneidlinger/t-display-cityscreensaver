#!/usr/bin/env python3
"""
Nocturnal City Evolution - Genetic Algorithm for Generative Art

This orchestrator creates a feedback loop:
1. Capture: Take screenshot of ESP32 display (manual for now)
2. Critique: Gemini Vision rates the aesthetics
3. Mutate: Claude Code modifies the simulation code
4. Deploy: PlatformIO compiles and flashes to ESP32
5. Repeat

Git-based evolution:
- 'seed' tag marks the original code (generation 0)
- Each evolution line (e.g., alpha, beta) gets its own branch family
- Branches: evo-{line}-{generation:03d} (e.g., evo-alpha-001)

Usage:
    python evolve.py                          # Run gen 1 on default line
    python evolve.py --line alpha             # Specify evolution line
    python evolve.py --line beta --gen 5      # Continue from gen 5
    python evolve.py --critique-only          # Just get scores, no mutation
    python evolve.py --status                 # Show evolution status
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# Optional imports - will check availability
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Warning: google-generativeai not installed. Run: pip install google-generativeai")

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    "project_root": Path(__file__).parent.parent,
    "source_file": "src/main.cpp",
    "sim_header": "include/CitySim.h",
    "captures_dir": Path(__file__).parent / "captures",
    "generations_dir": Path(__file__).parent / "generations",
    "platformio_env": "tdisplay",
    "gemini_model": "gemini-2.0-flash",
    "default_line": "alpha",
}

# ============================================================================
# GIT MANAGEMENT - Branch-based evolution tracking
# ============================================================================

def git_run(*args, check=True):
    """Run a git command and return output."""
    result = subprocess.run(
        ["git"] + list(args),
        cwd=CONFIG["project_root"],
        capture_output=True,
        text=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"Git command failed: {result.stderr}")
    return result

def get_current_branch() -> str:
    """Get the current git branch name."""
    result = git_run("rev-parse", "--abbrev-ref", "HEAD")
    return result.stdout.strip()

def branch_exists(branch_name: str) -> bool:
    """Check if a branch exists."""
    result = git_run("branch", "--list", branch_name, check=False)
    return bool(result.stdout.strip())

def get_branch_name(line: str, generation: int) -> str:
    """Generate branch name for a given line and generation."""
    return f"evo-{line}-{generation:03d}"

def get_latest_generation(line: str) -> int:
    """Find the latest generation number for an evolution line."""
    result = git_run("branch", "--list", f"evo-{line}-*", check=False)
    branches = result.stdout.strip().split("\n")
    branches = [b.strip().replace("* ", "") for b in branches if b.strip()]

    if not branches:
        return 0

    generations = []
    for b in branches:
        try:
            gen_num = int(b.split("-")[-1])
            generations.append(gen_num)
        except ValueError:
            continue

    return max(generations) if generations else 0

def create_generation_branch(line: str, generation: int, parent_branch: str = None):
    """Create a new branch for this generation."""
    branch_name = get_branch_name(line, generation)

    if branch_exists(branch_name):
        print(f"⚠️  Branch {branch_name} already exists, checking out...")
        git_run("checkout", branch_name)
        return branch_name

    # Determine parent branch
    if parent_branch is None:
        if generation == 1:
            parent_branch = "seed" if tag_exists("seed") else "main"
        else:
            parent_branch = get_branch_name(line, generation - 1)

    print(f"🌿 Creating branch {branch_name} from {parent_branch}")

    # Make sure we're on the parent branch first
    git_run("checkout", parent_branch)

    # Create and checkout new branch
    git_run("checkout", "-b", branch_name)

    return branch_name

def tag_exists(tag_name: str) -> bool:
    """Check if a tag exists."""
    result = git_run("tag", "--list", tag_name, check=False)
    return bool(result.stdout.strip())

def commit_generation(line: str, generation: int, critique: dict):
    """Commit the mutated code for this generation."""
    scores = critique.get("scores", {})
    overall = critique.get("overall_score", "?")

    # Stage changes
    git_run("add", "-A")

    # Check if there are changes to commit
    result = git_run("diff", "--cached", "--quiet", check=False)
    if result.returncode == 0:
        print("ℹ️  No changes to commit")
        return

    # Create commit message
    commit_msg = f"""Generation {generation} ({line} line)

Scores: {json.dumps(scores)}
Overall: {overall}/10

Critique: {critique.get('critique', 'N/A')}

🧬 Evolved with Nocturnal City Evolution
"""

    git_run("commit", "-m", commit_msg)
    print(f"✅ Committed generation {generation}")

def show_evolution_status():
    """Display the current evolution status."""
    print("\n" + "="*60)
    print("🧬 EVOLUTION STATUS")
    print("="*60)

    # Check for seed tag
    if tag_exists("seed"):
        print("\n✅ Seed tag exists")
    else:
        print("\n⚠️  No seed tag found. Run with --init to create it.")

    # Find all evolution lines
    result = git_run("branch", "--list", "evo-*", check=False)
    branches = result.stdout.strip().split("\n")
    branches = [b.strip().replace("* ", "") for b in branches if b.strip()]

    if not branches:
        print("\n📭 No evolution branches yet.")
        print("   Start with: python evolve.py --line alpha <image>")
        return

    # Group by line
    lines = {}
    for b in branches:
        parts = b.split("-")
        if len(parts) >= 3:
            line = parts[1]
            gen = int(parts[2])
            if line not in lines:
                lines[line] = []
            lines[line].append(gen)

    print(f"\n📊 Evolution Lines ({len(lines)} total):\n")
    for line, gens in sorted(lines.items()):
        latest = max(gens)
        print(f"   {line}: {len(gens)} generations (latest: {latest})")

        # Show recent generations
        recent = sorted(gens, reverse=True)[:5]
        for g in recent:
            branch = get_branch_name(line, g)
            current = " ← current" if branch == get_current_branch() else ""
            print(f"      └─ gen {g:03d}{current}")

    print(f"\n📍 Current branch: {get_current_branch()}")

# ============================================================================
# GEMINI CRITIC - Rates the visual aesthetics
# ============================================================================

CRITIC_PROMPT = """You are an expert in Generative Art Aesthetics and Urban Satellite Imagery.

Analyze this image of a generative "City at Night" simulation running on a tiny 1.14" LCD screen.
The simulation creates procedural city growth that should resemble night satellite imagery.

Rate the following aspects from 1-10:
1. **organic_growth**: Does the city sprawl look natural and organic, or rigid/artificial?
2. **luminance_balance**: Is the contrast between bright nodes and dim roads realistic?
3. **visual_interest**: Is it visually captivating? Does it draw the eye?
4. **density_distribution**: Is the city density well distributed, or too clustered/sparse?

Return ONLY a valid JSON object with this exact schema:
{
    "scores": {
        "organic_growth": <1-10>,
        "luminance_balance": <1-10>,
        "visual_interest": <1-10>,
        "density_distribution": <1-10>
    },
    "overall_score": <1-10>,
    "critique": "<2-3 sentences on what looks fake, cluttered, or could be improved>",
    "technical_suggestions": [
        "<specific algorithmic suggestion 1>",
        "<specific algorithmic suggestion 2>"
    ]
}
"""

def critique_image(image_path: str) -> dict:
    """Send image to Gemini Vision and get aesthetic critique."""
    if not GEMINI_AVAILABLE:
        print("ERROR: Gemini not available. Install with: pip install google-generativeai")
        return None

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable not set")
        return None

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(CONFIG["gemini_model"])

    # Upload and analyze image
    print(f"📸 Uploading image to Gemini: {image_path}")
    image_file = genai.upload_file(image_path)

    print("🔍 Analyzing aesthetics...")
    response = model.generate_content([image_file, CRITIC_PROMPT])

    # Parse JSON from response
    try:
        # Try to extract JSON from response
        text = response.text.strip()
        # Handle markdown code blocks
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse JSON response: {e}")
        print(f"Raw response: {response.text}")
        return {"raw_response": response.text, "parse_error": str(e)}


# ============================================================================
# CLAUDE CODE MUTATOR - Modifies the simulation code
# ============================================================================

MUTATOR_PROMPT_TEMPLATE = """The ESP32 city screensaver simulation was just evaluated by a Vision AI critic.

**Scores (1-10):**
{scores}

**Overall Score:** {overall}/10

**Critique:** {critique}

**Technical Suggestions:**
{suggestions}

Your task: Modify the CitySim simulation to improve the scores based on this feedback.

**Files you can modify:**
- src/main.cpp (rendering, colors, speed)
- include/CitySim.h (simulation logic, agents, growth patterns)

**STRICT RULES:**
1. Use TFT_eSPI library functions only
2. Keep within 240x135 resolution (landscape)
3. Keep it purely algorithmic - no external assets
4. Don't break the existing button controls or splash screen
5. Make targeted changes based on the critique - don't rewrite everything
6. Keep flash usage under 320KB

Focus on the lowest-scoring aspects first. Make 1-3 targeted improvements.
"""

def mutate_code(critique: dict) -> bool:
    """Use Claude Code to mutate the simulation based on critique."""
    if not critique or "scores" not in critique:
        print("ERROR: Invalid critique data")
        return False

    scores = critique.get("scores", {})
    scores_str = "\n".join([f"- {k}: {v}" for k, v in scores.items()])
    suggestions_str = "\n".join([f"- {s}" for s in critique.get("technical_suggestions", [])])

    prompt = MUTATOR_PROMPT_TEMPLATE.format(
        scores=scores_str,
        overall=critique.get("overall_score", "N/A"),
        critique=critique.get("critique", "No critique provided"),
        suggestions=suggestions_str or "- No specific suggestions"
    )

    print("🧬 Invoking Claude Code for mutation...")
    print(f"   Prompt length: {len(prompt)} chars")

    # Run claude code CLI
    result = subprocess.run(
        ["claude", "-p", prompt],
        cwd=CONFIG["project_root"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"ERROR: Claude Code failed: {result.stderr}")
        return False

    print("✅ Mutation complete")
    return True


# ============================================================================
# PLATFORMIO DEPLOYER - Compiles and flashes to ESP32
# ============================================================================

def build_and_flash(skip_flash: bool = False) -> bool:
    """Compile and upload to ESP32 using PlatformIO."""
    print("🔨 Building with PlatformIO...")

    # Build
    result = subprocess.run(
        ["python", "-m", "platformio", "run", "-e", CONFIG["platformio_env"]],
        cwd=CONFIG["project_root"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"ERROR: Build failed:\n{result.stderr}")
        return False

    print("✅ Build successful")

    if skip_flash:
        print("⏭️  Skipping flash (--skip-flash)")
        return True

    print("📤 Uploading to ESP32...")

    # Upload
    result = subprocess.run(
        ["python", "-m", "platformio", "run", "-e", CONFIG["platformio_env"], "-t", "upload"],
        cwd=CONFIG["project_root"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"ERROR: Upload failed:\n{result.stderr}")
        return False

    print("✅ Deployed to ESP32")
    return True


# ============================================================================
# EVOLUTION LOOP
# ============================================================================

def save_generation(line: str, generation: int, critique: dict):
    """Save generation data for history tracking."""
    gen_dir = CONFIG["generations_dir"] / line
    gen_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().isoformat()
    data = {
        "line": line,
        "generation": generation,
        "branch": get_branch_name(line, generation),
        "timestamp": timestamp,
        "critique": critique
    }

    filepath = gen_dir / f"gen_{generation:03d}.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    print(f"📁 Saved generation data to {filepath}")


def run_evolution_cycle(image_path: str, line: str, generation: int, skip_flash: bool = False) -> dict:
    """Run one complete evolution cycle."""
    print(f"\n{'='*60}")
    print(f"🧬 GENERATION {generation} (line: {line})")
    print(f"{'='*60}\n")

    # Step 0: Create branch for this generation
    print("PHASE 0: BRANCH SETUP")
    try:
        branch = create_generation_branch(line, generation)
        print(f"   On branch: {branch}\n")
    except RuntimeError as e:
        print(f"❌ Git error: {e}")
        return None

    # Step 1: Critique
    print("PHASE 1: CRITIQUE")
    critique = critique_image(image_path)
    if not critique:
        print("❌ Critique failed")
        return None

    print(f"\n📊 Scores: {critique.get('scores', {})}")
    print(f"📝 Critique: {critique.get('critique', 'N/A')}")

    # Save generation data
    save_generation(line, generation, critique)

    # Step 2: Mutate
    print("\nPHASE 2: MUTATE")
    if not mutate_code(critique):
        print("❌ Mutation failed")
        return critique

    # Step 3: Build & Deploy
    print("\nPHASE 3: BUILD & DEPLOY")
    if not build_and_flash(skip_flash):
        print("❌ Build/Deploy failed")
        return critique

    # Step 4: Commit
    print("\nPHASE 4: COMMIT")
    commit_generation(line, generation, critique)

    print(f"\n{'='*60}")
    print(f"✅ Generation {generation} complete!")
    print(f"   Branch: {get_branch_name(line, generation)}")
    print(f"   Take a new screenshot, then run:")
    print(f"   python evolve.py --line {line} --gen {generation + 1} <new_image>")
    print(f"{'='*60}\n")

    return critique


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Evolve the city screensaver using AI feedback",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python evolve.py screenshot.jpg                    # Start gen 1 on alpha line
  python evolve.py --line beta screenshot.jpg       # Start new beta line
  python evolve.py --line alpha --gen 5 img.jpg     # Continue alpha at gen 5
  python evolve.py --status                         # Show all evolution lines
  python evolve.py --critique-only screenshot.jpg   # Just get scores
        """
    )
    parser.add_argument("image", nargs="?", help="Path to screenshot image")
    parser.add_argument("--line", "-l", default=CONFIG["default_line"],
                        help=f"Evolution line name (default: {CONFIG['default_line']})")
    parser.add_argument("--gen", "-g", type=int, default=None,
                        help="Generation number (default: auto-detect next)")
    parser.add_argument("--critique-only", action="store_true",
                        help="Only run critique, no mutation")
    parser.add_argument("--skip-flash", action="store_true",
                        help="Skip the flash step")
    parser.add_argument("--status", action="store_true",
                        help="Show evolution status")

    args = parser.parse_args()

    # Ensure directories exist
    CONFIG["captures_dir"].mkdir(exist_ok=True)
    CONFIG["generations_dir"].mkdir(exist_ok=True)

    # Status command
    if args.status:
        show_evolution_status()
        return

    # Find image
    if not args.image:
        # Look for most recent capture
        captures = list(CONFIG["captures_dir"].glob("*.jpg")) + \
                   list(CONFIG["captures_dir"].glob("*.png")) + \
                   list(CONFIG["captures_dir"].glob("*.jpeg"))
        if captures:
            args.image = str(max(captures, key=os.path.getmtime))
            print(f"Using most recent capture: {args.image}")
        else:
            print("Usage: python evolve.py [options] <screenshot.jpg>")
            print(f"\nPlace screenshots in: {CONFIG['captures_dir']}")
            print("Or provide path as argument.")
            print("\nRun 'python evolve.py --status' to see evolution status.")
            sys.exit(1)

    # Auto-detect generation number
    if args.gen is None:
        args.gen = get_latest_generation(args.line) + 1
        print(f"Auto-detected generation: {args.gen}")

    # Critique only mode
    if args.critique_only:
        critique = critique_image(args.image)
        if critique:
            print("\n" + json.dumps(critique, indent=2))
        return

    # Full evolution cycle
    run_evolution_cycle(args.image, args.line, args.gen, args.skip_flash)


if __name__ == "__main__":
    main()
