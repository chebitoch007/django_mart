import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('🔨 Building cart TypeScript using dedicated config...');
console.log('Current directory:', __dirname);

try {
  // Use the dedicated cart TypeScript config
  console.log('🚀 Compiling TypeScript with tsconfig.cart.json...');
  execSync('npx tsc --project tsconfig.cart.json', {
    cwd: __dirname,
    stdio: 'inherit'
  });

  console.log('✅ Cart TypeScript compiled successfully');

  // Check the output directory
  const outputDir = path.join(__dirname, '../cart/static/cart/js');
  console.log(`📁 Checking output directory: ${outputDir}`);

  if (fs.existsSync(outputDir)) {
    const files = fs.readdirSync(outputDir);
    console.log(`📄 Files in directory: ${files.join(', ')}`);

    if (files.includes('cart-detail.js')) {
      const outputFile = path.join(outputDir, 'cart-detail.js');
      const content = fs.readFileSync(outputFile, 'utf8');
      console.log(`✅ cart-detail.js created successfully (${content.length} chars)`);
      console.log(`📁 Location: ${outputFile}`);

      // Check if it's ES module
      if (content.includes('export') || content.includes('import')) {
        console.log('🔍 Detected ES modules - template should use type="module"');
      } else {
        console.log('🔍 Detected regular script - can use standard script tag');
      }
    } else {
      console.log('❌ cart-detail.js not found in output directory');
    }
  } else {
    console.log('❌ Output directory does not exist');
  }

} catch (error) {
  console.error('❌ Failed to compile cart TypeScript:');
  console.error('Error message:', error.message);
  process.exit(1);
}