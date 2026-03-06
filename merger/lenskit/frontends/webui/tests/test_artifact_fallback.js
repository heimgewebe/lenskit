const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync('merger/lenskit/frontends/webui/app.js', 'utf8');

global.artifactListEl = {
    innerHTML: '',
    children: [],
    appendChild: function(c) { this.children.push(c); },
    querySelectorAll: function() { return []; }
};

const context = {
    window: {
        __RLENS_UI_VERSION__: 'test',
        location: { href: 'http://localhost' },
        addEventListener: () => {}
    },
    document: {
        body: { appendChild: () => {}, prepend: () => {} },
        createElement: (tag) => ({
            tagName: tag,
            className: '',
            dataset: {},
            children: [],
            appendChild: function(c) { this.children.push(c); },
            addEventListener: () => {},
            querySelectorAll: () => []
        }),
        getElementById: (id) => {
            if (id === 'artifactList') return global.artifactListEl;
            if (id === 'authToken') return { value: '' };
            return { value: '', innerText: '', addEventListener: () => {} };
        },
        querySelectorAll: () => [],
        addEventListener: () => {}
    },
    localStorage: { getItem: () => null, setItem: () => {}, clear: () => {} },
    sessionStorage: { getItem: () => null, setItem: () => {}, clear: () => {} },
    navigator: { serviceWorker: { getRegistrations: async () => [] } },
    console: {
        info: () => {},
        warn: () => {},
        error: (...args) => console.error("VM ERROR:", ...args),
        log: (...args) => console.log("VM LOG:", ...args)
    },
    alert: () => {},
    setTimeout: () => {},
    Date: Date,
    Object: Object,
    Array: Array,
    Set: Set,
    Map: Map,
    JSON: JSON,
    URL: URL,
    String: String,
    Promise: Promise,
    encodeURIComponent: encodeURIComponent,
    materializeRawFromCompressed: () => {},
    normalizePath: () => {},
    fetch: async (url, options) => {
        if (url.includes('/api/artifacts')) {
            return {
                ok: true, status: 200, json: async () => [{
                    id: '1', created_at: new Date().toISOString(), repos: ['repo1'], params: { level: 'l', mode: 'm' },
                    paths: {
                        json: 'a.json',
                        md: 'a.md',
                        chunk_index: 'chunk.json',
                        foo_bar: 'b.bin',
                        custom_bundle_x: 'c.zip'
                    }
                }]
            };
        }
        return { ok: true, status: 200, json: async () => ({}) };
    }
};

vm.createContext(context);

const code_patched = code.replace(
    /} catch \(e\) {\n        list.innerHTML = '<div class="text-red-500">Error loading artifacts.<\/div>';\n    }/,
    "} catch (e) {\n        console.error('Artifact load error:', e);\n        list.innerHTML = '<div class=\"text-red-500\">Error loading artifacts.</div>';\n    }"
);

vm.runInContext(code_patched, context);

async function runTest() {
    // 1. Test unit function formatArtifactFallbackLabel directly
    if (typeof context.formatArtifactFallbackLabel !== 'function') {
        console.error("FAIL: formatArtifactFallbackLabel is not defined in context");
        process.exit(1);
    }

    const t1 = context.formatArtifactFallbackLabel('foo_bar_baz');
    if (t1 !== 'Foo bar baz') {
        console.error("FAIL: expected 'Foo bar baz', got", t1);
        process.exit(1);
    }

    const t2 = context.formatArtifactFallbackLabel('custom_bundle_x');
    if (t2 !== 'Custom bundle x') {
        console.error("FAIL: expected 'Custom bundle x', got", t2);
        process.exit(1);
    }

    console.log("PASS: formatArtifactFallbackLabel unit checks");

    // 2. Test UI behavior
    await context.loadArtifacts();

    if (global.artifactListEl.children.length === 0) {
        console.error("FAIL: No children added to artifact list");
        process.exit(1);
    }

    const html = global.artifactListEl.children[0].innerHTML;

    if (!html.includes('key=foo_bar')) {
        console.error("FAIL: Should render foo_bar button");
        process.exit(1);
    }

    // Check known key behavior (chunk_index)
    if (!html.includes('Chunks')) {
        console.error("FAIL: Known keys should still use their explicit label");
        process.exit(1);
    }

    const match1 = html.match(/download\?key=foo_bar[^>]*>(.*?)<\/button>/);
    const label1 = match1 ? match1[1] : null;

    const match2 = html.match(/download\?key=custom_bundle_x[^>]*>(.*?)<\/button>/);
    const label2 = match2 ? match2[1] : null;

    if (label1 !== 'Foo bar') {
        console.error("FAIL: expected label 'Foo bar', got", label1);
        process.exit(1);
    }

    if (label2 !== 'Custom bundle x') {
        console.error("FAIL: expected label 'Custom bundle x', got", label2);
        process.exit(1);
    }

    console.log("PASS: loadArtifacts fallback rendering works perfectly!");
    process.exit(0);
}

runTest().catch(e => {
    console.error("test failed:", e);
    process.exit(1);
});
