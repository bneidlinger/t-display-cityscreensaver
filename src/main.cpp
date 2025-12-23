#include <Arduino.h>
#include <TFT_eSPI.h>
#include "Pins.h"
#include "CitySim.h"

// Landscape mode: 240 wide x 135 tall
static constexpr int SCREEN_W = 240;
static constexpr int SCREEN_H = 135;

// Sim grid matches screen (1:1 pixels)
static constexpr int GRID_W = 240;
static constexpr int GRID_H = 135;

TFT_eSPI tft = TFT_eSPI();
TFT_eSprite spr = TFT_eSprite(&tft);

CitySim city(GRID_W, GRID_H);

// Speed control: frames to skip between sim steps (higher = slower)
// Level 0: 1 step every 6 frames (~10 steps/sec) - very slow
// Level 1: 1 step every 2 frames (~30 steps/sec)
// Level 2: 1 step per frame (~60 steps/sec)
// Level 3: 3 steps per frame (~180 steps/sec)
static const uint8_t SPEED_FRAME_SKIP[] = {6, 2, 1, 1};
static const uint8_t SPEED_STEPS[] = {1, 1, 1, 3};
static const char* SPEED_NAMES[] = {"SLOW", "MED", "FAST", "TURBO"};
static uint8_t speedLevel = 0;  // Start at slowest
static uint8_t frameCount = 0;

// 80s synthwave colors
static const uint16_t NEON_PINK = 0xF81F;    // Hot pink
static const uint16_t NEON_CYAN = 0x07FF;    // Cyan
static const uint16_t NEON_PURPLE = 0x780F;  // Purple
static const uint16_t DARK_BLUE = 0x0008;    // Dark background

void showSplash() {
  spr.fillSprite(TFT_BLACK);

  // Dark gradient background (top to bottom: dark purple to black)
  for (int y = 0; y < SCREEN_H; y++) {
    uint8_t purple = (SCREEN_H - y) / 10;
    uint16_t col = tft.color565(purple, 0, purple * 2);
    spr.drawFastHLine(0, y, SCREEN_W, col);
  }

  // Scan lines for CRT effect
  for (int y = 0; y < SCREEN_H; y += 3) {
    spr.drawFastHLine(0, y, SCREEN_W, TFT_BLACK);
  }

  // Grid lines at bottom (synthwave horizon)
  int horizonY = 95;
  for (int y = horizonY; y < SCREEN_H; y += 8) {
    uint8_t brightness = (y - horizonY) * 2;
    uint16_t gridCol = tft.color565(brightness/3, 0, brightness);
    spr.drawFastHLine(0, y, SCREEN_W, gridCol);
  }
  // Vertical perspective lines
  for (int i = -4; i <= 4; i++) {
    int x1 = SCREEN_W/2 + i * 8;
    int x2 = SCREEN_W/2 + i * 40;
    spr.drawLine(x1, horizonY, x2, SCREEN_H, NEON_PURPLE);
  }

  // Sun (half circle at horizon)
  for (int r = 25; r > 0; r--) {
    uint8_t rCol = 255 - r * 4;
    uint8_t gCol = 100 - r * 2;
    uint16_t sunCol = tft.color565(rCol, gCol > 100 ? gCol : 0, r * 3);
    spr.drawCircle(SCREEN_W/2, horizonY + 5, r, sunCol);
  }
  // Clip sun below horizon
  spr.fillRect(0, horizonY + 6, SCREEN_W, SCREEN_H - horizonY, TFT_BLACK);
  // Redraw grid over clipped area
  for (int y = horizonY + 6; y < SCREEN_H; y += 8) {
    spr.drawFastHLine(0, y, SCREEN_W, NEON_PURPLE);
  }
  for (int i = -4; i <= 4; i++) {
    int x1 = SCREEN_W/2 + i * 8;
    int x2 = SCREEN_W/2 + i * 40;
    spr.drawLine(x1, horizonY, x2, SCREEN_H, NEON_PURPLE);
  }

  // DOS-style green title
  spr.setTextColor(TFT_GREEN);
  spr.drawString("esp_CITY_32", 55, 25, 4);

  // Author credit
  spr.setTextColor(tft.color565(0, 180, 0));  // Slightly dimmer green
  spr.drawString("by bneidlinger", 70, 60, 2);

  spr.pushSprite(0, 0);
  delay(2500);
}

// Map intensity -> “night satellite” color
// (keep it simple: dark blues for low, warm whites for high)
static inline uint16_t satColor(uint8_t v) {
  // Background almost black
  if (v < 10) return tft.color565(0, 0, 6);

  // Road glow region (cool)
  if (v < 80) {
    uint8_t b = 10 + (v / 3);
    uint8_t g = 4 + (v / 10);
    uint8_t r = 0;
    return tft.color565(r, g, b);
  }

  // City lights (warm)
  uint8_t x = v - 80; // 0..175
  uint8_t r = 30 + (x);
  uint8_t g = 22 + (x * 7) / 10;
  uint8_t b = 10 + (x * 2) / 10;

  r = (r > 255) ? 255 : r;
  g = (g > 255) ? 255 : g;
  b = (b > 255) ? 255 : b;

  return tft.color565(r, g, b);
}

void setupButtons() {
  pinMode(PIN_BTN_LEFT, INPUT_PULLUP);
  pinMode(PIN_BTN_RIGHT, INPUT); // GPIO35 has no pullups on many ESP32 boards
}

bool leftPressed() {
  return digitalRead(PIN_BTN_LEFT) == LOW;
}

bool rightPressed() {
  // Some boards wire right button active LOW too, but GPIO35 may float.
  // If it’s flaky, add external pullup or swap pin mapping.
  return digitalRead(PIN_BTN_RIGHT) == LOW;
}

void setup() {
  Serial.begin(115200);
  delay(200);

  setupButtons();

  tft.init();
  tft.setRotation(1); // try 1 or 3 if rotated weird
  tft.fillScreen(TFT_BLACK);

  // Backlight (if defined)
#ifdef TFT_BL
  pinMode(TFT_BL, OUTPUT);
  digitalWrite(TFT_BL, TFT_BACKLIGHT_ON);
#endif

  spr.createSprite(SCREEN_W, SCREEN_H);

  showSplash();
  city.reset();
}

void handleInput() {
  static uint32_t lastPress = 0;
  uint32_t now = millis();

  if (now - lastPress < 200) return;

  if (leftPressed()) {
    // Cycle through speed levels (0 -> 1 -> 2 -> 3 -> 0)
    speedLevel = (speedLevel + 1) % 4;
    lastPress = now;
  }

  if (rightPressed()) {
    showSplash();
    city.reset();
    lastPress = now;
  }
}

void drawFrame() {
  spr.fillSprite(TFT_BLACK);

  // Run sim steps based on speed level (with frame skipping for slow speeds)
  frameCount++;
  if (frameCount >= SPEED_FRAME_SKIP[speedLevel]) {
    frameCount = 0;
    for (int i = 0; i < SPEED_STEPS[speedLevel]; i++) {
      city.step();
    }
  }

  // Draw pixels
  for (int y = 0; y < GRID_H; y++) {
    for (int x = 0; x < GRID_W; x++) {
      uint8_t v = city.get(x, y);
      spr.drawPixel(x, y, satColor(v));
    }
  }

  // Minimal HUD
  spr.setTextColor(TFT_GREEN, TFT_BLACK);
  spr.drawString(SPEED_NAMES[speedLevel], 4, 4, 2);
  spr.drawString("L:speed  R:reset", 4, 20, 1);

  spr.pushSprite(0, 0);
}

void loop() {
  handleInput();
  drawFrame();
  delay(16); // ~60fps-ish. Raise this if it’s too busy.
}
