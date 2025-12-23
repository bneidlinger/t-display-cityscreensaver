#pragma once
#include <Arduino.h>

struct Agent {
  int16_t x, y;
  int8_t  dx, dy;
  uint8_t life;
};

class CitySim {
public:
  CitySim(uint16_t w, uint16_t h)
  : W(w), H(h) {
    grid = (uint8_t*)malloc(W * H);
    reset();
  }

  ~CitySim() {
    if (grid) free(grid);
  }

  void reset() {
    if (!grid) return;
    memset(grid, 0, W * H);
    agentCount = 0;

    // seed at center
    seedX = W / 2;
    seedY = H / 2;
    addAgent(seedX, seedY, 1, 0, 255);
    addAgent(seedX, seedY, 0, 1, 255);
    addAgent(seedX, seedY, -1, 0, 255);
    addAgent(seedX, seedY, 0, -1, 255);

    // initial “downtown”
    bloom(seedX, seedY, 6, 120);
    steps = 0;
    nextBrightNodeStep = 400 + (esp_random() % 600);
  }

  // One simulation tick (do multiple per frame for speed)
  void step() {
    steps++;

    // Occasionally drop a bright node (“stadium/dense district”)
    if (steps >= nextBrightNodeStep) {
      placeBrightNode();
      nextBrightNodeStep = steps + 600 + (esp_random() % 1200);
    }

    // Update agents
    for (uint8_t i = 0; i < agentCount; i++) {
      Agent &a = agents[i];
      if (a.life == 0) continue;

      // “road” mark
      addIntensity(a.x, a.y, 35);

      // chance to add lights along roads
      if ((esp_random() % 100) < 25) addIntensity(a.x, a.y, 45);

      // random turn
      uint32_t r = esp_random() % 1000;
      if (r < 40) { // left turn
        int8_t ndx = -a.dy;
        int8_t ndy = a.dx;
        a.dx = ndx; a.dy = ndy;
      } else if (r < 80) { // right turn
        int8_t ndx = a.dy;
        int8_t ndy = -a.dx;
        a.dx = ndx; a.dy = ndy;
      }

      // branch sometimes (increased rate for more road network)
      if (agentCount < MAX_AGENTS && (esp_random() % 1000) < 30) {
        // spawn a new agent turned left/right
        int8_t ndx = (esp_random() & 1) ? -a.dy : a.dy;
        int8_t ndy = (ndx == -a.dy) ? a.dx : -a.dx;
        addAgent(a.x, a.y, ndx, ndy, 140 + (esp_random() % 100));
      }

      // move
      a.x += a.dx;
      a.y += a.dy;

      // bounce off edges
      if (a.x < 1 || a.x >= (int16_t)W-1 || a.y < 1 || a.y >= (int16_t)H-1) {
        a.x = constrain(a.x, 1, (int16_t)W-2);
        a.y = constrain(a.y, 1, (int16_t)H-2);
        // turn around-ish
        a.dx = -a.dx;
        a.dy = -a.dy;
        a.life = (a.life > 30) ? (a.life - 30) : 0;
      } else {
        // life decay
        if (a.life) a.life--;
      }

      // If dead, respawn frequently to keep growth going
      if (a.life == 0 && (esp_random() % 100) < 15) {
        respawnAgent(a);
      }
    }

    // Very slow decay - only every 500 steps, decay by 1
    if ((steps % 500) == 0) decay(1);

    // Safety net: ensure minimum active agents to keep roads drawing
    uint8_t activeCount = 0;
    for (uint8_t i = 0; i < agentCount; i++) {
      if (agents[i].life > 0) activeCount++;
    }

    // If too few active, force respawn some dead agents
    if (activeCount < 8) {
      for (uint8_t i = 0; i < agentCount && activeCount < 12; i++) {
        if (agents[i].life == 0) {
          respawnAgent(agents[i]);
          activeCount++;
        }
      }
    }
  }

  uint8_t get(uint16_t x, uint16_t y) const {
    return grid[y * W + x];
  }

  uint16_t width()  const { return W; }
  uint16_t height() const { return H; }

private:
  void addAgent(int16_t x, int16_t y, int8_t dx, int8_t dy, uint8_t life) {
    if (agentCount >= MAX_AGENTS) return;
    agents[agentCount++] = Agent{x, y, dx, dy, life};
  }

  void respawnAgent(Agent &a) {
    // Try to respawn near existing lit areas (not just center)
    int16_t bestX = seedX, bestY = seedY;
    uint8_t bestVal = 0;

    // Sample random spots, pick one with some light
    for (uint8_t tries = 0; tries < 15; tries++) {
      int16_t rx = 2 + (esp_random() % (W - 4));
      int16_t ry = 2 + (esp_random() % (H - 4));
      uint8_t v = get(rx, ry);
      if (v > bestVal && v < 200) {  // Has light but not saturated
        bestVal = v;
        bestX = rx;
        bestY = ry;
      }
    }

    static const int8_t dirs[4][2] = {{1,0},{-1,0},{0,1},{0,-1}};
    uint8_t d = esp_random() % 4;
    a.x = bestX;
    a.y = bestY;
    a.dx = dirs[d][0];
    a.dy = dirs[d][1];
    a.life = 200 + (esp_random() % 55);  // Longer life
  }

  void addIntensity(int16_t x, int16_t y, uint8_t amt) {
    uint16_t idx = (uint16_t)y * W + (uint16_t)x;
    uint16_t v = grid[idx] + amt;
    grid[idx] = (v > 255) ? 255 : (uint8_t)v;
  }

  void decay(uint8_t amt) {
    for (uint32_t i = 0; i < (uint32_t)W * H; i++) {
      uint8_t v = grid[i];
      grid[i] = (v > amt) ? (v - amt) : 0;
    }
  }

  void bloom(int16_t cx, int16_t cy, uint8_t radius, uint8_t strength) {
    for (int16_t y = -radius; y <= radius; y++) {
      for (int16_t x = -radius; x <= radius; x++) {
        int16_t px = cx + x;
        int16_t py = cy + y;
        if (px < 1 || px >= (int16_t)W-1 || py < 1 || py >= (int16_t)H-1) continue;
        int16_t d2 = x*x + y*y;
        if (d2 > radius*radius) continue;

        // stronger in center
        uint8_t add = strength - (uint8_t)(min<int16_t>(strength, d2 * 3));
        addIntensity(px, py, add);
      }
    }
  }

  void placeBrightNode() {
    // pick a spot biased toward existing activity
    int16_t bestX = seedX, bestY = seedY;
    uint8_t best = 0;

    for (uint8_t tries = 0; tries < 20; tries++) {
      int16_t x = 2 + (esp_random() % (W - 4));
      int16_t y = 2 + (esp_random() % (H - 4));
      uint8_t v = get(x, y);
      if (v > best) { best = v; bestX = x; bestY = y; }
    }

    // stadium core + halo
    bloom(bestX, bestY, 10, 220);
    bloom(bestX, bestY, 18, 90);

    // spawn extra agents around it for “district growth”
    for (uint8_t i = 0; i < 5 && agentCount < MAX_AGENTS; i++) {
      int16_t rx = bestX + (int16_t)((int32_t)(esp_random() % 21) - 10);
      int16_t ry = bestY + (int16_t)((int32_t)(esp_random() % 21) - 10);
      rx = constrain(rx, 2, (int16_t)W-3);
      ry = constrain(ry, 2, (int16_t)H-3);

      static const int8_t dirs[4][2] = {{1,0},{-1,0},{0,1},{0,-1}};
      uint8_t d = esp_random() % 4;
      addAgent(rx, ry, dirs[d][0], dirs[d][1], 200 + (esp_random() % 55));
    }
  }

private:
  const uint16_t W, H;
  uint8_t *grid = nullptr;

  static constexpr uint8_t MAX_AGENTS = 60;
  Agent agents[MAX_AGENTS];
  uint8_t agentCount = 0;

  int16_t seedX = 0, seedY = 0;
  uint32_t steps = 0;
  uint32_t nextBrightNodeStep = 0;
};
