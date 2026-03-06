import re

with open("merger/lenskit/architecture/graph_index.py", "r") as f:
    code = f.read()
code = code.replace("from typing import Dict, Any, Set, List", "from typing import Dict, Any")
with open("merger/lenskit/architecture/graph_index.py", "w") as f:
    f.write(code)

with open("merger/lenskit/retrieval/query_core.py", "r") as f:
    code2 = f.read()
code2 = code2.replace("from typing import Dict, Any, Optional, List", "from typing import Dict, Any, Optional")
with open("merger/lenskit/retrieval/query_core.py", "w") as f:
    f.write(code2)
