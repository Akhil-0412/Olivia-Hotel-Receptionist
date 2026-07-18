import sys

with open("src/mcp_server.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix join newlines
content = content.replace('return "\n".join(lines)', 'return "\\n".join(lines)')
content = content.replace('f"Booking Details:\n" + "\n".join(', 'f"Booking Details:\\n" + "\\n".join(')
content = content.replace('return "\n".join(msgs)', 'return "\\n".join(msgs)')

# Fix f-string newlines
content = content.replace('"\n        f"', '\\n"\n        f"')

with open("src/mcp_server.py", "w", encoding="utf-8") as f:
    f.write(content)
