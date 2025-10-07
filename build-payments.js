// build-payments.js
const fs = require('fs');
const path = require('path');

console.log('Building payment system...');

// Function to add .js extensions to imports
function fixImports(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf8');

    // Fix import statements
    let fixedContent = content.replace(
      /from\s+['"](\.\/[^'"]+)['"]/g,
      (match, importPath) => {
        if (!importPath.endsWith('.js') && !importPath.startsWith('http')) {
          return `from '${importPath}.js'`;
        }
        return match;
      }
    );

    // Fix export statements
    fixedContent = fixedContent.replace(
      /export\s+\*\s+from\s+['"](\.\/[^'"]+)['"]/g,
      (match, importPath) => {
        if (!importPath.endsWith('.js')) {
          return `export * from '${importPath}.js'`;
        }
        return match;
      }
    );

    fs.writeFileSync(filePath, fixedContent, 'utf8');
    console.log(`✓ Fixed imports in: ${filePath}`);
  } catch (error) {
    console.log(`✗ Error processing ${filePath}:`, error.message);
  }
}

// Files to process
const filesToFix = [
  'static/js/payments.js',
  'static/js/payment-methods/mpesa.js',
  'static/js/payment-methods/paypal.js',
  'static/js/ui/ui.js',
  'static/js/utils/utils.js'
];

console.log('Fixing module imports...');
filesToFix.forEach(file => {
  if (fs.existsSync(file)) {
    fixImports(file);
  } else {
    console.log(`✗ File not found: ${file}`);
  }
});

console.log('Build completed!');