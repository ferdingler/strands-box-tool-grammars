"""Parse stripe-cli pkg/cmd/resources/specs_gen.go into JSON: {VarName: {name,path,method,params:{prop:type}}}."""
import json, re, sys
src = open(sys.argv[1]).read()
out = {}
for m in re.finditer(r'^var (\w+) = resource\.OperationSpec\{\n(.*?)^\}\n', src, re.M | re.S):
    var, body = m.group(1), m.group(2)
    name = re.search(r'^\tName:\s+"([^"]+)"', body, re.M).group(1)
    path = re.search(r'^\tPath:\s+"([^"]+)"', body, re.M).group(1)
    method = re.search(r'^\tMethod:\s+"([^"]+)"', body, re.M).group(1)
    params = {}
    for pm in re.finditer(r'^\t\t"([^"]+)": \{\n(.*?)^\t\t\},?\n', body, re.M | re.S):
        t = re.search(r'Type:\s+"([^"]+)"', pm.group(2))
        params[pm.group(1)] = t.group(1) if t else None
    out[var] = {"name": name, "path": path, "method": method, "params": params}
json.dump(out, sys.stdout, indent=1, sort_keys=True)
