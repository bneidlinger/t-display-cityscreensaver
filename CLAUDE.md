# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ESP32-based city screensaver for the TTGO T-Display (ST7789 135x240 LCD). Simulates procedural city growth resembling night satellite imagery using agent-based road/light generation.

## Build Commands

This is a PlatformIO project. Copy `starter_platformio.ini` to `platformio.ini` before building:

```bash
# Build
pio run -e tdisplay

# Upload to device
pio run -e tdisplay -t upload

# Serial monitor
pio device monitor -b 115200
```

## Architecture

**Core simulation (`include/CitySim.h`)**: Agent-based city generator. Multiple `Agent` structs move across a 2D intensity grid, depositing "road" brightness as they travel. Agents randomly turn, branch into new agents, and respawn when expired. Periodic "bright nodes" create stadium/district hotspots that attract new growth.

**Rendering (`src/main.cpp`)**: Uses TFT_eSPI with a sprite buffer. The `satColor()` function maps grid intensity values to a night-satellite color palette (dark blues for background, warm whites for city lights). Runs 25 simulation steps per frame for visible growth speed.

**Hardware pins (`include/Pins.h`)**: GPIO0 = left button (pause/resume), GPIO35 = right button (reset simulation).

**Configuration (`include/config.h`)**: Tunable constants for grid dimensions, frame timing, bright node frequency, and intensity values. Note: `main.cpp` also defines its own `SCREEN_W`/`SCREEN_H`/`GRID_W`/`GRID_H` constants that may differ.

## Hardware Target

TTGO T-Display ESP32 with ST7789 1.14" LCD. Pin mappings in `starter_platformio.ini` build flags configure TFT_eSPI library at compile time.
