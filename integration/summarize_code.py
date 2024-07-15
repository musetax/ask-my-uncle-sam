import os
import ast
import re

def summarize_script(file_path):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
        
        tree = ast.parse(content)
        summary = f"Summary of {os.path.basename(file_path)}:\n"
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                summary += f"- Function: {node.name}\n"
            elif isinstance(node, ast.ClassDef):
                summary += f"- Class: {node.name}\n"
        
        return summary
    except Exception as e:
        return f"Unable to summarize {os.path.basename(file_path)}: {str(e)}"

def summarize_readme(file_path):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
        
        # Remove Markdown headers
        content = re.sub(r'#+\s', '', content)
        # Remove Markdown links
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
        # Remove code blocks
        content = re.sub(r'```[\s\S]*?```', '', content)
        
        summary = "README Summary:\n"
        summary += "\n".join(line.strip() for line in content.split('\n') if line.strip())
        return summary
    except Exception as e:
        return f"Unable to summarize README file: {str(e)}"

def process_repository(repo_path):
    result = ""
    
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, repo_path)
            result += f"\nFile: {relative_path}\n"
            
            if file.endswith('.py'):
                result += summarize_script(file_path) + "\n"
            elif file.lower() in ['readme', 'readme.md', 'readme.txt']:
                result += summarize_readme(file_path) + "\n"
    
    return result

if __name__ == "__main__":
    # Get the current script's directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Navigate up one level to the main repository directory
    repo_path = os.path.dirname(current_dir)
    
    output = process_repository(repo_path)
    print(output)

    # Save the output to a file in the same directory as the script
    output_file = os.path.join(current_dir, 'repo_summary.txt')
    with open(output_file, 'w') as f:
        f.write(output)
    print(f"Summary saved to {output_file}")