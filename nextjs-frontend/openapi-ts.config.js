const { defineConfig } = require("@hey-api/openapi-ts");

module.exports = defineConfig({
  // Input: the OpenAPI JSON written by the backend into the shared volume
  input: "./shared-data/openapi.json",
  output: {
    path: "./src/lib",
    format: "prettier",
  },
  client: "@hey-api/client-fetch",
});
