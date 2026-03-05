const fs = require('fs');

let code = fs.readFileSync('merger/lenskit/frontends/webui/app.js', 'utf8');

// 1. applyPickerSelection
const target1 = `function applyPickerSelection() {
    if (!currentPickerTarget) return;

    // Store token (opaque) in data attribute if target supports it (e.g. Atlas),
    // or value if appropriate.
    // For Atlas, we need to send the token.
    // For Hub (Legacy/JobRequest), we typically send the path string.
    // BUT: The goal is to satisfy CodeQL. Hub config is less dynamic.
    // Let's adopt a hybrid approach:
    // 1. Set visible value to path (for user confirmation/display)
    // 2. Set 'data-token' attribute on the input to the token.
    // Consumers (startAtlasJob) will check for data-token.

    const el = document.getElementById(currentPickerTarget);
    if (el) {
        el.value = currentPickerPath || '';
        el.dataset.token = currentPickerToken || '';
    }

    closePicker();
}`;
const replace1 = `function applyPickerSelection() {
    if (!currentPickerTarget) return;

    // Store token (opaque) in data attribute if target supports it (e.g. Atlas),
    // or value if appropriate.
    // For Atlas, we need to send the token.
    // For Hub (Legacy/JobRequest), we typically send the path string.
    // BUT: The goal is to satisfy CodeQL. Hub config is less dynamic.
    // Let's adopt a hybrid approach:
    // 1. Set visible value to path (for user confirmation/display)
    // 2. Set 'data-token' attribute on the input to the token.
    // Consumers (startAtlasJob) will check for data-token.

    const el = document.getElementById(currentPickerTarget);
    if (el) {
        el.value = currentPickerPath || '';
        el.dataset.token = currentPickerToken || '';
    }

    // If hub changed, reload repos
    if (currentPickerTarget === 'hubPath') {
        fetchRepos(currentPickerPath);
    }

    closePicker();
}`;

code = code.replace(target1, replace1);

// 2. pickerSelect
const target2 = `function pickerSelect() {
    if (currentPickerTarget && currentPickerPath) {
        document.getElementById(currentPickerTarget).value = currentPickerPath;

        // If hub changed, reload repos
        if (currentPickerTarget === 'hubPath') {
            fetchRepos(currentPickerPath);
        }

        closePicker();
    }
}`;
const replace2 = `function pickerSelect() {
    applyPickerSelection();
}`;

code = code.replace(target2, replace2);

// 3. buildAtlasPayload extraction
const target3 = `async function startAtlasJob(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.innerText = "Scanning...";

    const rootInput = document.getElementById('atlasRoot');
    const rootPath = rootInput.value.trim();
    const rootToken = rootInput.dataset.token; // Use token if available from picker

    // Save Atlas Config (include token for restoration)
    // NOTE: Persisting the token is a deliberate UX decision for this Localhost tool.
    // It allows the form to remain valid after a page reload.
    // In a multi-user environment, persisting capabilities in localStorage would be a risk.
    const config = {
        version: 2,
        root: rootPath,
        token: rootToken || null,
        depth: document.getElementById('atlasDepth').value,
        limit: document.getElementById('atlasLimit').value,
        excludes: document.getElementById('atlasExcludes').value
    };
    localStorage.setItem(ATLAS_CONFIG_KEY, JSON.stringify(config));

    // Determine Root Strategy
    let payloadToken = rootToken || null;
    let payloadId = null;

    // Check for explicit ID keywords
    const lower = rootPath.toLowerCase();
    if (['hub', 'merges', 'system', 'home'].includes(lower)) {
        payloadId = lower === 'home' ? 'system' : lower;
        payloadToken = null; // Explicit ID overrides token
    }

    const payload = {
        root_token: payloadToken,
        root_id: payloadId,

        max_depth: parseInt(config.depth),
        max_entries: parseInt(config.limit),
        exclude_globs: config.excludes.split(',').map(s => s.trim())
    };

    if (!payload.root_token && !payload.root_id) {`;

const replace3 = `function buildAtlasPayload(rootPath, rootToken, depth, limit, excludes) {
    let payloadToken = rootToken || null;
    let payloadId = null;

    const lower = (rootPath || "").trim().toLowerCase();
    if (['hub', 'merges', 'system', 'home'].includes(lower)) {
        payloadId = lower === 'home' ? 'system' : lower;
        payloadToken = null; // Explicit ID overrides token
    }

    return {
        root_token: payloadToken,
        root_id: payloadId,
        max_depth: parseInt(depth, 10) || 6,
        max_entries: parseInt(limit, 10) || 200000,
        exclude_globs: excludes ? excludes.split(',').map(s => s.trim()).filter(Boolean) : []
    };
}

async function startAtlasJob(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.innerText = "Scanning...";

    const rootInput = document.getElementById('atlasRoot');
    const rootPath = rootInput.value.trim();
    const rootToken = rootInput.dataset.token; // Use token if available from picker

    // Save Atlas Config (include token for restoration)
    // NOTE: Persisting the token is a deliberate UX decision for this Localhost tool.
    // It allows the form to remain valid after a page reload.
    // In a multi-user environment, persisting capabilities in localStorage would be a risk.
    const config = {
        version: 2,
        root: rootPath,
        token: rootToken || null,
        depth: document.getElementById('atlasDepth').value,
        limit: document.getElementById('atlasLimit').value,
        excludes: document.getElementById('atlasExcludes').value
    };
    localStorage.setItem(ATLAS_CONFIG_KEY, JSON.stringify(config));

    const payload = buildAtlasPayload(
        config.root,
        config.token,
        config.depth,
        config.limit,
        config.excludes
    );

    if (!payload.root_token && !payload.root_id) {`;

code = code.replace(target3, replace3);

// 4. input event listener
const target4 = `    document.getElementById('jobForm').addEventListener('submit', startJob);
    document.getElementById('atlasForm').addEventListener('submit', startAtlasJob);
});

// --- Tabs ---`;

const replace4 = `    document.getElementById('jobForm').addEventListener('submit', startJob);
    document.getElementById('atlasForm').addEventListener('submit', startAtlasJob);

    // Clear token if user manually edits the root path
    const atlasRootEl = document.getElementById('atlasRoot');
    if (atlasRootEl) {
        atlasRootEl.addEventListener('input', (e) => {
            delete e.target.dataset.token;
        });
    }
});

// --- Tabs ---`;

code = code.replace(target4, replace4);

fs.writeFileSync('merger/lenskit/frontends/webui/app.js', code);
console.log('Patched app.js');
