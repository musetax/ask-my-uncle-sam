import os
import re

def summarize_code(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
        content = file.read()
    
    summary = f"File: {file_path}\n"
    
    if file_path.endswith('.py'):
        # Python
        functions = re.findall(r'def\s+(\w+)\s*\(.*?\):\s*(\"{3}[\s\S]*?\"{3}|\'{3}[\s\S]*?\'{3})?', content)
        for func_name, docstring in functions:
            summary += f"  Function: {func_name}\n"
            if docstring:
                summary += f"    Description: {docstring.strip('\"\'')}\n"
    
    elif file_path.endswith('.ts') or file_path.endswith('.js'):
        # TypeScript and JavaScript
        functions = re.findall(r'(function\s+(\w+)|(\w+)\s*=\s*function|\(.*?\)\s*=>\s*{)', content)
        for func in functions:
            func_name = func[1] or func[2] or "Anonymous Function"
            summary += f"  Function: {func_name}\n"
        
        # Look for classes
        classes = re.findall(r'class\s+(\w+)', content)
        for class_name in classes:
            summary += f"  Class: {class_name}\n"
    
    return summary

def explore_directory(directory):
    summary = ""
    for root, dirs, files in os.walk(directory):
        level = root.replace(directory, '').count(os.sep)
        indent = ' ' * 4 * level
        summary += f"{indent}{os.path.basename(root)}/\n"
        sub_indent = ' ' * 4 * (level + 1)
        for file in files:
            if file.endswith(('.py', '.ts', '.js')):
                file_path = os.path.join(root, file)
                summary += f"{sub_indent}{file}\n"
                summary += summarize_code(file_path)
    return summary

# Usage
directory_path = "/Users/samuellarson/muse/GitHub/ask-my-uncle-sam"
result = explore_directory(directory_path)
print(result)

# Optionally, save to a file
with open("code_summary.txt", "w", encoding='utf-8') as f:
    f.write(result)