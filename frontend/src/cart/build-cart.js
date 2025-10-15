import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('🔨 Building cart TypeScript...');
console.log('Current directory:', __dirname);

try {
  // Use the local tsconfig.json which has proper ES module settings
  const result = execSync('npx tsc --project tsconfig.json', {
    cwd: __dirname,
    encoding: 'utf8'
  });

  console.log('✅ Cart TypeScript compiled successfully');

  // Check multiple possible output locations
  const possibleOutputDirs = [
    path.join(__dirname, '../../../../cart/static/cart/js'),
    path.join(__dirname, '../../../cart/static/cart/js'),
    path.join(__dirname, '../../cart/static/cart/js'),
    path.join(__dirname, '../cart/static/cart/js'),
    path.join(__dirname, 'cart/static/cart/js'),
    path.join(process.cwd(), 'cart/static/cart/js')
  ];

  let found = false;
  for (const outputDir of possibleOutputDirs) {
    if (fs.existsSync(outputDir)) {
      console.log(`📁 Found directory: ${outputDir}`);
      const files = fs.readdirSync(outputDir);
      console.log(`📄 Files in directory: ${files.join(', ')}`);

      if (files.includes('cart-detail.js')) {
        console.log(`✅ cart-detail.js found at: ${outputDir}`);
        found = true;

        // Check the content
        const content = fs.readFileSync(path.join(outputDir, 'cart-detail.js'), 'utf8');
        console.log(`📝 File size: ${content.length} characters`);
        console.log(`🔍 First 50 chars: ${content.substring(0, 50)}`);
      }
    }
  }

  if (!found) {
    console.log('❌ cart-detail.js not found in any expected location');
    console.log('🔍 Checking current working directory:', process.cwd());
    console.log('🔍 Files in current directory:', fs.readdirSync(process.cwd()));
  }

} catch (error) {
  console.error('❌ Failed to compile cart TypeScript:', error.message);
  console.error('Stack:', error.stack);
  process.exit(1);
}