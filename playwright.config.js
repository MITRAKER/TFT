import { defineConfig } from "@playwright/test";

const port = 8765;
const onCi = Boolean(process.env.CI);

export default defineConfig({
  testDir: "tests/web/e2e",
  timeout: 90_000,
  retries: onCi ? 1 : 0,
  workers: 1,
  reporter: onCi ? [["github"], ["list"]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: "retain-on-failure",
  },
  webServer: {
    command: `python -m tft serve --port ${port} --rules tests/web/e2e/short-rules.toml`,
    url: `http://127.0.0.1:${port}/api/health`,
    reuseExistingServer: !onCi,
    timeout: 30_000,
  },
});
