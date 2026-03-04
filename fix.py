with open("merger/lenskit/frontends/webui/app.js", "r") as f:
    c = f.read()

old_block = """    const planOnlyChecked = document.getElementById('planOnly').checked;
    const commonPayload = {
        force_new: !planOnlyChecked,
        hub: document.getElementById('hubPath').value,"""

new_block = """    const planOnlyChecked = document.getElementById('planOnly').checked;
    const commonPayload = {
        hub: document.getElementById('hubPath').value,"""

c = c.replace(old_block, new_block)

old_block2 = """        extensions: extensions,
        extras: extrasCsv
    };"""

new_block2 = """        extensions: extensions,
        extras: extrasCsv
    };

    if (!planOnlyChecked) {
        commonPayload.force_new = true;
    }"""

c = c.replace(old_block2, new_block2)

with open("merger/lenskit/frontends/webui/app.js", "w") as f:
    f.write(c)
