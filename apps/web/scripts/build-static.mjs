import { copyFileSync, existsSync, readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const apiUrl = process.env.NEXT_PUBLIC_API_URL;

function createRoutePayloadAliases(directory) {
  let aliasesCreated = 0;

  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (!entry.isDirectory()) {
      continue;
    }

    const entryPath = path.join(directory, entry.name);
    if (!entry.name.startsWith("__next.")) {
      aliasesCreated += createRoutePayloadAliases(entryPath);
      continue;
    }

    const pending = [entryPath];
    while (pending.length > 0) {
      const current = pending.pop();
      for (const child of readdirSync(current, { withFileTypes: true })) {
        const childPath = path.join(current, child.name);
        if (child.isDirectory()) {
          pending.push(childPath);
          continue;
        }

        const relativeName = path.relative(entryPath, childPath).split(path.sep).join(".");
        copyFileSync(childPath, path.join(directory, `${entry.name}.${relativeName}`));
        aliasesCreated += 1;
      }
    }
  }

  return aliasesCreated;
}

if (!apiUrl) {
  console.error("NEXT_PUBLIC_API_URL is required for a static production build.");
  process.exit(1);
}

let parsedApiUrl;
try {
  parsedApiUrl = new URL(apiUrl);
} catch {
  console.error(`NEXT_PUBLIC_API_URL is not a valid URL: ${apiUrl}`);
  process.exit(1);
}

if (parsedApiUrl.protocol !== "https:" || parsedApiUrl.hostname === "localhost") {
  console.error("NEXT_PUBLIC_API_URL must be a public HTTPS URL for a static production build.");
  process.exit(1);
}

const nextCli = path.join(webRoot, "node_modules", "next", "dist", "bin", "next");
const result = spawnSync(process.execPath, [nextCli, "build"], {
  cwd: webRoot,
  env: {
    ...process.env,
    ATLAS_STATIC_EXPORT: "true",
    NEXT_PUBLIC_API_URL: parsedApiUrl.origin,
  },
  stdio: "inherit",
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}

if (result.status !== 0) {
  process.exit(result.status ?? 1);
}

const outputRoot = path.join(webRoot, "out");
const indexFile = path.join(outputRoot, "index.html");
if (!existsSync(indexFile)) {
  console.error(`Static export did not create ${indexFile}.`);
  process.exit(1);
}

copyFileSync(path.join(webRoot, "public", ".htaccess"), path.join(outputRoot, ".htaccess"));
const routePayloadAliases = createRoutePayloadAliases(outputRoot);
console.log(`\nFileZilla package ready: ${outputRoot}`);
console.log(`Created ${routePayloadAliases} route payload aliases for shared static hosting.`);
console.log("Upload the contents of this directory, including .htaccess, to public_html.");
