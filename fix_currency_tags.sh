#!/bin/bash

echo "🔍 Checking for duplicate currency_tags.py files..."

# Find all currency_tags.py files
files=$(find . -path "*/templatetags/currency_tags.py" -type f)

echo "Found files:"
echo "$files"

# Remove core version if exists
if [ -f "core/templatetags/currency_tags.py" ]; then
    echo "⚠️  Removing duplicate in core/templatetags/"
    mv core/templatetags/currency_tags.py core/templatetags/currency_tags.py.backup
    echo "✅ Backed up to currency_tags.py.backup"
fi

# Clear cache
echo "🧹 Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null
rm -rf store/templatetags/__pycache__

echo "✅ Done! Now restart your server."