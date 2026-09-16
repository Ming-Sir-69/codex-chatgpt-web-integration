/** Prepare the same native tunnel profile used by setup, without touching the live route.
 * Used when an authenticated launcher is available but its GUI is locked.
 * This does not create/verify the ChatGPT connector and does not claim tool acceptance.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { atomicWriteFile, getConfigDir, getConfigPath, loadConfig } from "../src/config";
import { runDoctor } from "../src/doctor";
import { createTunnelConfig, installRuntimeKey, installTunnelClient, connectTunnel,
  waitForTunnelReady, stopTunnel } from "../src/tunnel";

const current = loadConfig();
if (current.mode !== "browser-only" || current.browserHost !== "launcher"
  || current.browserInteractionMode !== "automatic") {
  throw new Error("Staging requires an existing authenticated Automatic browser-only launcher");
}
const before = readFileSync(getConfigPath());
const doctor = await runDoctor();
if (!doctor.ok) throw new Error("Existing deployment must pass doctor before staging Full mode");
const core = getConfigDir();
const credentials = join(core, "local-credentials");
const tunnelId = readFileSync(join(credentials, "tunnel-id.txt"), "utf8").trim();
const runtimeKeyFile = installRuntimeKey(join(credentials, "runtime-key.txt"));
const tunnel = createTunnelConfig({ binaryPath: await installTunnelClient(), tunnelId, runtimeKeyFile });
const config = { ...current, mode: "full" as const, tunnel, automaticTunnel: tunnel };
try {
  connectTunnel(config);
  const ready = await waitForTunnelReady(config);
  if (!ready.ok) throw new Error(`Tunnel is not ready: ${ready.detail}`);
  atomicWriteFile(join(core, "full-mode-staged.json"), JSON.stringify({
    previousSha256: createHash("sha256").update(before).digest("hex"),
    preparedAt: new Date().toISOString(),
    tunnelReadyVerified: true,
    config,
  }, null, 2) + "\n");
  console.log("Full config staged; actual Tunnel readiness verified. ChatGPT connector still requires binding.");
} finally {
  stopTunnel(config);
}
