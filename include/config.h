#pragma once
#include <Arduino.h>

// Landscape mode: 240 wide x 135 tall
constexpr int SCREEN_W = 240;
constexpr int SCREEN_H = 135;

// Sim grid matches screen (1:1 pixels)
constexpr int GRID_W = 240;
constexpr int GRID_H = 135;

// Growth pacing
constexpr uint16_t STEPS_PER_FRAME = 20;     // how many growth ops per render
constexpr uint16_t FRAME_MS = 33;            // ~30 FPS cap

// Bright node (stadium/district) behavior
constexpr uint32_t BRIGHT_NODE_MIN_MS = 20'000;  // at least every ~20s
constexpr uint32_t BRIGHT_NODE_MAX_MS = 60'000;  // at most every ~60s
constexpr uint8_t  BRIGHT_NODE_RADIUS_MIN = 3;
constexpr uint8_t  BRIGHT_NODE_RADIUS_MAX = 9;

// Night satellite vibe
constexpr uint8_t DECAY_PER_STEP = 0;     // 0 = persistent city, >0 slowly fades
constexpr uint8_t ROAD_STRENGTH  = 35;    // brightness added per road pixel
constexpr uint8_t HUB_STRENGTH   = 120;   // brightness added in “bright node”
