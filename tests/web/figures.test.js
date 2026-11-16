import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { IDLE_SECONDS, phaseOf } from "../../src/tft/web/figures.js";

const CLOSE = 1e-9;

describe("the phase of a figure in its standing loop", () => {
  it("is a delay that starts the loop part of the way in", () => {
    for (const seconds of [0, 0.3, 1.6, 12.34, 3600.5]) {
      for (const salt of [0, 3, 27]) {
        const phase = phaseOf("Hodl Hamster", salt, seconds);
        assert.ok(phase <= 0 && phase > -IDLE_SECONDS, `phase ${phase}`);
      }
    }
  });

  it("follows the clock, so a figure drawn again carries on where it was", () => {
    const start = phaseOf("Pip Squeak", 5, 10);
    const later = phaseOf("Pip Squeak", 5, 10.4);
    const moved = (((start - later) % IDLE_SECONDS) + IDLE_SECONDS) % IDLE_SECONDS;
    assert.ok(Math.abs(moved - 0.4) < CLOSE);
    assert.ok(Math.abs(phaseOf("Pip Squeak", 5, 10 + IDLE_SECONDS) - start) < 1e-6);
  });

  it("spreads figures by name and by cell", () => {
    const names = ["Pip Squeak", "Index Drone", "Hodl Hamster", "Barrel Bo", "Coupon Clerk"];
    const phases = new Set(names.map((name) => phaseOf(name, 0, 0).toFixed(3)));
    assert.ok(phases.size >= 3, `only ${phases.size} different phases`);
    assert.notEqual(phaseOf("Barrel Bo", 0, 0), phaseOf("Barrel Bo", 1, 0));
    assert.notEqual(phaseOf("Barrel Bo", 0, 0), phaseOf("Barrel Bo", 7, 0));
  });
});
