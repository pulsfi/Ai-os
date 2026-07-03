// Central config loader — reads "09 Automation/.env" (all keys optional),
// falls back to scripts/config.json, then to free public endpoints.
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const DIR = dirname(fileURLToPath(import.meta.url)); // 09 Automation/lib
const ENV_PATH = join(DIR, "..", ".env");
if (existsSync(ENV_PATH)) process.loadEnvFile(ENV_PATH);

const cfgPath = join(DIR, "..", "scripts", "config.json");
const legacy = existsSync(cfgPath) ? JSON.parse(readFileSync(cfgPath, "utf8")) : {};

const env = (k) => (process.env[k] || "").trim();

export const CONFIG = {
  rpcUrl:
    env("SOLANA_RPC_URL") ||
    (env("HELIUS_API_KEY")
      ? `https://mainnet.helius-rpc.com/?api-key=${env("HELIUS_API_KEY")}`
      : "") ||
    legacy.rpcUrl ||
    "https://api.mainnet-beta.solana.com",
  walletAddress: env("WALLET_ADDRESS") || legacy.walletAddress || "",
  birdeyeApiKey: env("BIRDEYE_API_KEY") || legacy.birdeyeApiKey || "",
  coingeckoApiKey: env("COINGECKO_API_KEY") || "",
  jupiterApiKey: env("JUPITER_API_KEY") || "",
  alertThreshold: Number(env("ALERT_THRESHOLD") || legacy.alertThreshold || 10),
};
