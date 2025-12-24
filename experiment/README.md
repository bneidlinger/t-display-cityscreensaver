# Nocturnal City Evolution Experiment

An autonomous feedback loop for evolving generative art using Vision AI (Gemini) and Code AI (Claude Code).

## The Loop

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   ESP32 runs simulation                                     │
│            │                                                │
│            ▼                                                │
│   📸 Capture screenshot (manual for now)                    │
│            │                                                │
│            ▼                                                │
│   🔍 Gemini Vision critiques aesthetics                     │
│      Returns: scores, critique, suggestions                 │
│            │                                                │
│            ▼                                                │
│   🧬 Claude Code mutates the code                           │
│      Based on: critique feedback                            │
│            │                                                │
│            ▼                                                │
│   🔨 PlatformIO builds & flashes                            │
│            │                                                │
│            ▼                                                │
│   📝 Git commits to generation branch                       │
│            │                                                │
│            └──────────────► REPEAT                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Git-Based Evolution

Each evolution is tracked in git branches:

```
seed (tag) ─── Original code (generation 0)
    │
    ├── evo-alpha-001 ──► evo-alpha-002 ──► evo-alpha-003 ──► ...
    │                                           │
    │                                           └── ESP32 #1
    │
    └── evo-beta-001 ──► evo-beta-002 ──► evo-beta-003 ──► ...
                                              │
                                              └── ESP32 #2
```

- **seed**: Tagged original code, never modified
- **Evolution lines**: Parallel branches (alpha, beta, gamma...) for multiple ESP32s
- **Generation branches**: Each mutation gets its own branch
- **Full history**: `git diff evo-alpha-001..evo-alpha-010` to see evolution

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set your Gemini API key:
```bash
# Windows
set GEMINI_API_KEY=your_api_key_here

# Linux/Mac
export GEMINI_API_KEY=your_api_key_here
```

3. Ensure Claude Code CLI is installed and authenticated.

4. Ensure PlatformIO is installed.

## Usage

### Check evolution status:
```bash
python evolve.py --status
```

### Run first evolution (starts at gen 1):
```bash
python evolve.py screenshot.jpg
```

### Run on a specific evolution line:
```bash
python evolve.py --line alpha screenshot.jpg   # Default line
python evolve.py --line beta screenshot.jpg    # Parallel evolution
python evolve.py --line gamma screenshot.jpg   # Another parallel
```

### Continue a specific generation:
```bash
python evolve.py --line alpha --gen 5 screenshot.jpg
```

### Critique only (no code changes):
```bash
python evolve.py --critique-only screenshot.jpg
```

### Skip flashing (just mutate and commit):
```bash
python evolve.py --skip-flash screenshot.jpg
```

## Workflow Example

```bash
# 1. Start with seed code running on ESP32
#    Take a screenshot, save as capture1.jpg

# 2. Run first evolution
python evolve.py --line alpha capture1.jpg
# Creates branch: evo-alpha-001
# Gemini critiques, Claude mutates, PlatformIO flashes

# 3. Observe the new behavior, take another screenshot
#    Save as capture2.jpg

# 4. Run next generation (auto-detects gen 2)
python evolve.py --line alpha capture2.jpg
# Creates branch: evo-alpha-002

# 5. Repeat!

# 6. To compare generations:
git diff evo-alpha-001..evo-alpha-005

# 7. To go back to a previous generation:
git checkout evo-alpha-003
pio run -t upload

# 8. To reset to seed:
git checkout seed
pio run -t upload
```

## Parallel Evolution (Multiple ESP32s)

Run different evolution lines on different devices:

```bash
# ESP32 #1 - Alpha line
python evolve.py --line alpha screenshot_esp1.jpg

# ESP32 #2 - Beta line
python evolve.py --line beta screenshot_esp2.jpg

# ESP32 #3 - Gamma line
python evolve.py --line gamma screenshot_esp3.jpg
```

Each line evolves independently. You can cross-breed later by merging branches!

## Folder Structure

```
experiment/
├── evolve.py               # Main orchestrator
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── captures/               # Put screenshots here
│   ├── alpha_gen001.jpg
│   ├── alpha_gen002.jpg
│   └── ...
└── generations/            # Evolution history (auto-created)
    ├── alpha/
    │   ├── gen_001.json
    │   ├── gen_002.json
    │   └── ...
    └── beta/
        └── ...
```

## Gemini Scoring Criteria

The Vision AI rates on four aspects (1-10):

| Metric | Description |
|--------|-------------|
| **organic_growth** | Natural city sprawl vs rigid patterns |
| **luminance_balance** | Contrast between nodes and roads |
| **visual_interest** | How captivating is it? |
| **density_distribution** | Clustering vs spread |

## Tips

1. **Consistent screenshots** - Same lighting, angle, timing (after ~5 min of growth)
2. **Review changes** - Check `git diff` after each mutation
3. **Revert bad mutations** - `git checkout seed -- src/ include/`
4. **Cross-breed** - Merge interesting branches together
5. **Track scores** - Watch for improvement trends in generations/*.json
