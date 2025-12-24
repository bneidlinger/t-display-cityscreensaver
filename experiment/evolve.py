#!/usr/bin/env python3
"""
Nocturnal City Evolution - Genetic Algorithm for Generative Art

This orchestrator creates a feedback loop:
1. Capture: Take screenshot of ESP32 display (manual for now)
2. Critique: Gemini Vision rates the aesthetics
3. Mutate: Claude Code modifies the simulation code
4. Deploy: PlatformIO compiles and flashes to ESP32
5. Repeat

Usage:
    python evolve.py              # Run one evolution cycle
    python evolve.py --loop 10    # Run 10 generations
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
    "generation": 0,
}

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

def build_and_flash() -> bool:
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

def save_generation(generation: int, critique: dict):
    """Save generation data for history tracking."""
    gen_dir = CONFIG["generations_dir"]
    gen_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().isoformat()
    data = {
        "generation": generation,
        "timestamp": timestamp,
        "critique": critique
    }

    filepath = gen_dir / f"gen_{generation:04d}.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    print(f"📁 Saved generation data to {filepath}")


def run_evolution_cycle(image_path: str, generation: int) -> dict:
    """Run one complete evolution cycle."""
    print(f"\n{'='*60}")
    print(f"🧬 GENERATION {generation}")
    print(f"{'='*60}\n")

    # Step 1: Critique
    print("PHASE 1: CRITIQUE")
    critique = critique_image(image_path)
    if not critique:
        print("❌ Critique failed")
        return None

    print(f"\n📊 Scores: {critique.get('scores', {})}")
    print(f"📝 Critique: {critique.get('critique', 'N/A')}")

    # Save generation data
    save_generation(generation, critique)

    # Step 2: Mutate
    print("\nPHASE 2: MUTATE")
    if not mutate_code(critique):
        print("❌ Mutation failed")
        return critique

    # Step 3: Deploy
    print("\nPHASE 3: DEPLOY")
    if not build_and_flash():
        print("❌ Deploy failed")
        return critique

    print(f"\n✅ Generation {generation} complete!")
    print("   Take a new screenshot after observing the changes.")

    return critique


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Evolve the city screensaver using AI feedback")
    parser.add_argument("image", nargs="?", help="Path to screenshot image")
    parser.add_argument("--generation", "-g", type=int, default=1, help="Generation number")
    parser.add_argument("--critique-only", action="store_true", help="Only run critique, no mutation")
    parser.add_argument("--skip-flash", action="store_true", help="Skip the flash step")

    args = parser.parse_args()

    # Ensure directories exist
    CONFIG["captures_dir"].mkdir(exist_ok=True)
    CONFIG["generations_dir"].mkdir(exist_ok=True)

    if not args.image:
        # Look for most recent capture
        captures = list(CONFIG["captures_dir"].glob("*.jpg")) + list(CONFIG["captures_dir"].glob("*.png"))
        if captures:
            args.image = str(max(captures, key=os.path.getmtime))
            print(f"Using most recent capture: {args.image}")
        else:
            print("Usage: python evolve.py <screenshot.jpg>")
            print(f"\nPlace screenshots in: {CONFIG['captures_dir']}")
            print("Or provide path as argument.")
            sys.exit(1)

    if args.critique_only:
        critique = critique_image(args.image)
        if critique:
            print(json.dumps(critique, indent=2))
    else:
        run_evolution_cycle(args.image, args.generation)


if __name__ == "__main__":
    main()
