import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  // Input: the OpenAPI JSON written by the backend into the shared volume
  input: "./shared-data/openapi.json",
  output: {
    path: "./src/lib",
    format: "prettier",
  },
  client: "@hey-api/client-fetch",
});
