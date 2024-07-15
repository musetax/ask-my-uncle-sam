import os
import ast
import re

def summarize_script(file_path):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
        
        tree = ast.parse(content)
        summary = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                summary.append(f"Function: {node.name}")
            elif isinstance(node, ast.ClassDef):
                summary.append(f"Class: {node.name}")
        
        return summary if summary else ["No functions or classes found"]
    except Exception as e:
        return [f"Unable to summarize: {str(e)}"]

def summarize_readme(file_path):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
        
        content = re.sub(r'#+\s', '', content)
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
        content = re.sub(r'```[\s\S]*?```', '', content)
        
        summary = ' '.join(line.strip() for line in content.split('\n') if line.strip())
        return summary[:500] + "..." if len(summary) > 500 else summary
    except Exception as e:
        return f"Unable to summarize README: {str(e)}"

def process_repository(repo_path):
    structure = {}
    readmes = []
    script_summaries = {}
    
    for root, dirs, files in os.walk(repo_path):
        rel_dir = os.path.relpath(root, repo_path)
        if rel_dir == '.':
            rel_dir = 'root'
        
        structure[rel_dir] = []
        for file in files:
            if file.lower() in ['readme', 'readme.md', 'readme.txt']:
                readmes.append((rel_dir, summarize_readme(os.path.join(root, file))))
            elif file.endswith('.py'):
                summary = summarize_script(os.path.join(root, file))
                if summary != ["No functions or classes found"]:
                    script_summaries[f"{rel_dir}/{file}"] = summary
            structure[rel_dir].append(file)
    
    result = "Repository Structure:\n"
    for dir, files in structure.items():
        result += f"{dir}/\n"
        for file in files:
            result += f"  {file}\n"
    
    result += "\nREADME Summaries:\n"
    for dir, summary in readmes:
        result += f"{dir} README: {summary}\n\n"
    
    result += "\nScript Summaries:\n"
    for script, summary in script_summaries.items():
        result += f"{script}:\n"
        for item in summary:
            result += f"  {item}\n"
        result += "\n"
    
    return result

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_path = os.path.dirname(current_dir)
    
    output = process_repository(repo_path)
    print(output)

    output_file = os.path.join(current_dir, 'repo_summary.txt')
    with open(output_file, 'w') as f:
        f.write(output)
    print(f"Summary saved to {output_file}")