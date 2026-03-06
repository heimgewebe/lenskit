import json
import jsonschema

with open("merger/lenskit/contracts/query-result.v1.schema.json", "r") as f:
    schema = json.load(f)

print("Properties of why block:")
print(json.dumps(schema["properties"]["results"]["items"]["properties"]["why"], indent=2))
