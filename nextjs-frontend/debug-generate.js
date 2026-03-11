const path = require('path');

process.on('unhandledRejection', (err) => {
  console.error('Unhandled rejection:', err);
  process.exit(1);
});

async function main() {
  try {
    const { createClient } = require(
      path.resolve(
        __dirname,
        'node_modules/.pnpm/@hey-api+openapi-ts@0.83.1_typescript@5.9.3/node_modules/@hey-api/openapi-ts/dist/index.cjs'
      )
    );

    const result = await createClient({
      input: './shared-data/openapi.json',
      output: {
        path: './src/lib',
        format: 'prettier',
      },
      plugins: ['@hey-api/typescript', '@hey-api/sdk', '@hey-api/client-fetch'],
    });

    console.log('Success:', JSON.stringify(result, null, 2));
  } catch (err) {
    console.error('Error:', err);
    process.exit(1);
  }
}

main();
