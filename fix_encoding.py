# fix_encoding.py
try:
    # Try reading as UTF-16LE (the wrong encoding)
    with open('requirements.txt', 'r', encoding='utf-16le') as f:
        content = f.read()

    # Write back as proper UTF-8
    with open('requirements.txt', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully converted requirements.txt to UTF-8")
except Exception as e:
    print(f"Error: {str(e)}")
    print("Make sure the file exists and is in UTF-16LE format")