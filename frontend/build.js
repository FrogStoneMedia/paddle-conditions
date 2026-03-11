import esbuild from "esbuild";

const watch = process.argv.includes("--watch");

const options = {
  entryPoints: ["src/paddle-cards.js"],
  bundle: true,
  outfile: "../custom_components/paddle_conditions/frontend/dist/paddle-cards.js",
  format: "esm",
  minify: !watch,
  sourcemap: watch,
  target: ["es2021"],
  logLevel: "info",
};

if (watch) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
  console.log("Watching for changes...");
} else {
  await esbuild.build(options);
}
