// The outer runner waits for Playwright's servers to stop before proving that
// all database fixtures/ACL/metadata were restored. No secret is printed.
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const root = path.resolve(frontend, "..");
const python = path.join(root, "backend", ".venv", "Scripts", "python.exe");
function snapshot() {
  const result = spawnSync(python, ["-B", "-m", "backend.tests.auth_browser_server", "--snapshot"], { cwd: root, encoding: "utf8" });
  if (result.status !== 0) throw new Error("Browser-test DB snapshot failed; credentials are not printed");
  return JSON.parse(result.stdout.trim());
}

let status = 1;
try {
  const before = snapshot();
  if (before.fixture_connections !== 0) throw new Error("A browser rollback fixture is already running");
  const result = spawnSync(process.execPath, [path.join(frontend, "node_modules", "@playwright", "test", "cli.js"), "test", ...process.argv.slice(2)], {
    cwd: frontend, stdio: "inherit", env: { ...process.env, SPMS_ADVISOR_FIXTURE_TAG: randomUUID().replaceAll("-", "") },
  });
  const after = snapshot();
  const restored = before.metadata_sha256 === after.metadata_sha256
    && JSON.stringify(before.row_counts) === JSON.stringify(after.row_counts)
    && after.fixture_connections === 0;
  console.log(JSON.stringify({ browser_database_rollback: restored ? "PASS" : "FAIL", fixture_connections: after.fixture_connections, identity_sequence_values_excluded: true }));
  status = result.status === 0 && restored ? 0 : 1;
} catch {
  console.error("Auth browser-test setup/cleanup failed; no credentials or connection URLs are printed.");
}
process.exitCode = status;
