import { existsSync, rmSync } from "node:fs";
import { join } from "node:path";
import { spawn } from "node:child_process";

const frontendRoot = process.cwd();
const nextDir = join(frontendRoot, ".next-dev");

if (existsSync(nextDir)) {
  rmSync(nextDir, { recursive: true, force: true });
  console.log("[dev] Cleared stale .next-dev directory");
}

const nextBin = join(frontendRoot, "node_modules", "next", "dist", "bin", "next");
const cliArgs = process.argv.slice(2);
const hasPortArg = cliArgs.includes("--port") || cliArgs.includes("-p");
const hasHostnameArg = cliArgs.includes("--hostname") || cliArgs.includes("-H");
const defaultArgs = [
  ...(hasHostnameArg ? [] : ["--hostname", "127.0.0.1"]),
  ...(hasPortArg ? [] : ["--port", "3000"]),
];
const child = spawn(process.execPath, [nextBin, "dev", ...defaultArgs, ...cliArgs], {
  stdio: "inherit",
  env: process.env,
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }

  process.exit(code ?? 0);
});
