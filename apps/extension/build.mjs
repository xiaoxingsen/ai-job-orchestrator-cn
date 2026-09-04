import { cp, mkdir, rm } from "node:fs/promises";
import { resolve } from "node:path";
import { build } from "esbuild";


const root = import.meta.dirname;
const dist = resolve(root, "dist");
await rm(dist, { recursive: true, force: true });
await mkdir(dist, { recursive: true });

await Promise.all([
  build({
    entryPoints: [resolve(root, "src/background.ts")],
    outfile: resolve(dist, "background.js"),
    bundle: true,
    format: "esm",
    platform: "browser",
    target: "chrome120",
    sourcemap: true,
  }),
  build({
    entryPoints: [resolve(root, "src/content.ts")],
    outfile: resolve(dist, "content.js"),
    bundle: true,
    format: "iife",
    platform: "browser",
    target: "chrome120",
    sourcemap: true,
  }),
  build({
    entryPoints: [resolve(root, "src/popup.ts")],
    outfile: resolve(dist, "popup.js"),
    bundle: true,
    format: "iife",
    platform: "browser",
    target: "chrome120",
    sourcemap: true,
  }),
]);

await Promise.all([
  cp(resolve(root, "public/manifest.json"), resolve(dist, "manifest.json")),
  cp(resolve(root, "popup.html"), resolve(dist, "popup.html")),
]);

