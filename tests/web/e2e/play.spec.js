import { expect, test } from "@playwright/test";

const MAX_ROUNDS = 14;

/** Collect what the page logs; refused actions show up as 4xx resources and are expected. */
function watchForProblems(page) {
  const problems = [];
  page.on("pageerror", (error) => problems.push(`page error: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("status of 4")) {
      problems.push(`console error: ${message.text()}`);
    }
  });
  return problems;
}

async function startMatch(page, { seed, bots }) {
  await page.goto("/");
  await expect(page.locator("#brand")).toHaveText("Team Fight Tackticktics");
  await page.fill("#opt-seed", String(seed));
  await page.locator("#opt-bots").fill(String(bots));
  await page.click("#btn-play");
  await expect(page.locator("#shop .card")).toHaveCount(5);
}

async function buyAndField(page) {
  const affordable = page.locator("#shop .card:not(.empty):not(.poor)");
  if ((await affordable.count()) > 0 && (await page.locator("#bench .slot:not(.occupied)").count()) > 0) {
    await affordable.first().click();
    await expect(page.locator("#toast")).toContainText("bought");
  }
  const [fielded, limit] = (await page.locator("#board-count").textContent()).split("/").map(Number);
  if (fielded < limit && (await page.locator("#bench .slot.occupied").count()) > 0) {
    await page.locator("#bench .slot.occupied").first().click();
    await expect(page.locator("#board")).toHaveClass(/targeting/);
    await page.locator('#board .hex[data-row="3"]:not(.occupied) .tile').first().click();
    await expect(page.locator("#toast")).toContainText("fielded");
  }
}

test("a match can be played to the end and its replay downloaded", async ({ page }) => {
  const problems = watchForProblems(page);
  await startMatch(page, { seed: 11, bots: 3 });
  await expect(page.locator("#round-info")).toContainText("Round 1-1");

  let finished = false;
  for (let round = 0; round < MAX_ROUNDS && !finished; round += 1) {
    if (await page.locator("#overlay:not([hidden]) .offer").first().isVisible()) {
      await page.locator("#overlay .offer").first().click();
      await expect(page.locator("#overlay")).toBeHidden();
    }
    await buyAndField(page);
    await page.click("#btn-fight");
    const next = page.locator("#dialog-actions button.primary");
    await expect(next).toBeVisible();
    await expect(page.locator("#dialog-body")).toContainText("What this round teaches");
    finished = (await next.textContent()).includes("Final");
    await next.click();
  }

  expect(finished).toBe(true);
  await expect(page.locator("#dialog-title")).toContainText("Match over: you placed");
  await expect(page.locator("#dialog-body .place")).toHaveCount(4);
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download replay" }).click(),
  ]);
  expect(download.suggestedFilename()).toBe("tft-replay-seed-11.json");
  await page.getByRole("button", { name: "Back to the lobby" }).click();
  await expect(page.locator("#match-list .match-row").first()).toContainText("finished");
  expect(problems).toEqual([]);
});

test("the first round shows the trade, the lessons and the market slice", async ({ page }) => {
  const problems = watchForProblems(page);
  await startMatch(page, { seed: 7, bots: 7 });
  await buyAndField(page);
  await expect(page.locator("#board .hex.occupied")).toHaveCount(1);
  await page.click("#btn-preview");
  await expect(page.locator("#dialog-title")).toHaveText("Odds on replayed market slices");
  await expect(page.locator("#dialog-body .place")).toHaveCount(7);
  await page.getByRole("button", { name: "Close" }).click();
  await page.click("#btn-fight");
  await expect(page.locator("#dialog-body")).toContainText("market slice");
  await expect(page.locator("#dialog-body table.trades tbody tr")).toHaveCount(1);
  await expect(page.locator("#dialog-body table.trades svg.spark .spark-line")).toHaveCount(1);
  await expect(page.locator("#dialog-body table.trades tbody td").nth(7)).toHaveText(/%|wiped out/);
  await expect(page.locator("#dialog-body .other-board table.theirs tbody tr")).toHaveCount(2);
  await expect(page.locator("#dialog-body .move")).toHaveCount(6);
  await expect(page.locator("#dialog-body .fights li").first()).toBeVisible();
  expect(problems).toEqual([]);
});

test("the table shows the stage, the players and original art for every unit", async ({ page }) => {
  const problems = watchForProblems(page);
  await page.goto("/");
  await expect(page.locator("#showcase .token svg.art")).toHaveCount(25);
  await startMatch(page, { seed: 5, bots: 7 });
  await expect(page.locator("#stage .round")).toHaveCount(3);
  await expect(page.locator("#stage .round.current")).toHaveText("1-1");
  await expect(page.locator("#rivals .rival")).toHaveCount(8);
  await expect(page.locator("#rivals .rival.me")).toContainText("You");
  await expect(page.locator("#shop .card .card-art svg.art")).toHaveCount(5);
  await buyAndField(page);
  await expect(page.locator("#board .hex.occupied .token .disc svg.art")).toHaveCount(1);
  await page.locator("#board .hex.occupied .token").click();
  await expect(page.locator("#detail")).toContainText("Sell");
  await page.locator("#rivals .rival:not(.me)").first().click();
  await expect(page.locator("#dialog-body .board.mini")).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();
  expect(problems).toEqual([]);
});

test("a fight plays as a scene with both boards before the result", async ({ page }) => {
  const problems = watchForProblems(page);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await startMatch(page, { seed: 9, bots: 7 });
  await buyAndField(page);
  await page.click("#btn-fight");
  await expect(page.locator("#theatre")).toBeVisible();
  await expect(page.locator("#scene-caption")).toContainText("Round 1-1: You against The Market");
  await expect(page.locator("#scene-mine .hex.occupied .token")).toHaveCount(1);
  await expect(page.locator("#scene-enemy .hex.occupied .token")).toHaveCount(2);
  await expect(page.locator("#scene-mine .token .trace .spark-line")).toBeVisible();
  await expect(page.locator("#scene-floor")).toHaveAttribute("data-phase", "resolved");
  await expect(page.locator("#scene-mine .token .verdict")).toHaveText(/%|wiped out/);
  await expect(page.locator("#banner")).toBeVisible();
  await expect(page.locator("#banner .banner-word")).toHaveText(/Victory|Defeat|Draw/);
  await expect(page.locator("#dialog-actions button.primary")).toBeVisible();
  await expect(page.locator("#theatre")).toBeHidden();
  await page.locator("#dialog-actions button.primary").click();

  await buyAndField(page);
  await page.click("#btn-fight");
  await expect(page.locator("#theatre")).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page.locator("#theatre")).toBeHidden();
  await expect(page.locator("#dialog-actions button.primary")).toBeVisible();
  expect(problems).toEqual([]);
});

test("a bot match can be watched round by round", async ({ page }) => {
  const problems = watchForProblems(page);
  await page.goto("/");
  await page.locator("#opt-bots").fill("3");
  await page.click("#btn-watch");
  await expect(page.locator("#seats .seat-card")).toHaveCount(4);
  await page.click("#btn-step");
  await expect(page.locator("#spectate-fights")).toContainText("Round 1-1");
  await page.click("#btn-step");
  await expect(page.locator("#spectate-fights")).toContainText("Round 1-2");
  await expect(page.locator("#seats .board.mini .hex.occupied").first()).toBeVisible();
  expect(problems).toEqual([]);
});

test("on a narrow screen the shop sits right under the bench", async ({ page }) => {
  await page.setViewportSize({ width: 420, height: 820 });
  await startMatch(page, { seed: 3, bots: 2 });
  const bench = await page.locator("#bench").boundingBox();
  const shop = await page.locator("#shop").boundingBox();
  const traits = await page.locator("#traits").boundingBox();
  expect(shop.y).toBeGreaterThanOrEqual(bench.y + bench.height);
  expect(traits.y).toBeGreaterThan(shop.y + shop.height);
  const pageWidth = await page.evaluate("document.documentElement.scrollWidth");
  expect(pageWidth).toBeLessThanOrEqual(420);
});
