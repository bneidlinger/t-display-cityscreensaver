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
│            └──────────────► REPEAT                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

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

### Run one evolution cycle:
```bash
# Place a screenshot in captures/ folder, then:
python evolve.py

# Or specify image directly:
python evolve.py screenshot.jpg
```

### Critique only (no code changes):
```bash
python evolve.py screenshot.jpg --critique-only
```

### Skip flashing (just mutate code):
```bash
python evolve.py screenshot.jpg --skip-flash
```

### Track generations:
```bash
python evolve.py captures/gen1.jpg --generation 1
python evolve.py captures/gen2.jpg --generation 2
# etc...
```

## Folder Structure

```
experiment/
├── evolve.py           # Main orchestrator
├── requirements.txt    # Python dependencies
├── captures/           # Put screenshots here
└── generations/        # Evolution history (auto-created)
    ├── gen_0001.json
    ├── gen_0002.json
    └── ...
```

## How It Works

### Gemini Critic
Rates the simulation on:
- **organic_growth**: Natural city sprawl vs rigid patterns
- **luminance_balance**: Contrast between nodes and roads
- **visual_interest**: How captivating is it?
- **density_distribution**: Clustering vs spread

### Claude Mutator
Receives the scores and critique, then makes targeted modifications to:
- `src/main.cpp` - Rendering, colors, speed
- `include/CitySim.h` - Simulation logic, agents, growth

### Evolution History
Each generation saves a JSON file with:
- Timestamp
- All scores
- Critique text
- Suggestions made

## Tips

1. **Take consistent screenshots** - Same lighting, angle, timing
2. **Let it run** - Capture after 5+ minutes of growth
3. **Review changes** - Check git diff after each mutation
4. **Revert if needed** - `git checkout -- src/` to undo bad mutations
