import ast, subprocess, difflib
REPO='E:/Projects/SAS'
old = subprocess.run(['git','-C',REPO,'show','d3640e3:serve_dashboard.py'],capture_output=True,check=True).stdout.decode('utf-8')
new = open(REPO+'/serve_dashboard.py',encoding='utf-8').read()
def blank(tree):
    n=0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id=='HTML' for t in node.targets):
            node.value = ast.Constant(value='')
            n+=1
    return n
to, tn = ast.parse(old), ast.parse(new)
print('HTML assigns blanked', blank(to), blank(tn))
do, dn = ast.dump(to, indent=1), ast.dump(tn, indent=1)
print('AST equal with HTML blanked:', do==dn)
diff = [l for l in difflib.unified_diff(do.splitlines(), dn.splitlines(), lineterm='', n=2)]
print('\n'.join(diff[:60]))
def fn(tree, name):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name==name:
            return ast.dump(node)
for name in ['_build_evaluation','_capture_frame','_cell_color','_slim_panel','_resolve_role_count_params','_resolve_seed','_start','_step']:
    print(name, 'AST identical:', fn(to,name)==fn(tn,name))
# BUILTIN_SCENARIOS
def assign(tree, name):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id==name for t in node.targets):
            return ast.dump(node)
print('BUILTIN_SCENARIOS identical:', assign(to,'BUILTIN_SCENARIOS')==assign(tn,'BUILTIN_SCENARIOS'))
