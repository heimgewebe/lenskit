const { buildAtlasPayload } = require('../atlas_payload.js');

let failed = 0;

function assert(condition, message) {
    if (!condition) {
        console.error("FAIL: " + message);
        failed++;
    } else {
        console.log("PASS: " + message);
    }
}

// Test 1: "hub" without token
let payload = buildAtlasPayload("hub", undefined, "6", "200000", "");
assert(payload.root_id === "hub", "root_id should be 'hub'");
assert(payload.root_token === null, "root_token should be null");

// Test 2: "HUB " (case insensitive and trim)
payload = buildAtlasPayload("HUB ", null, 6, 200000, "");
assert(payload.root_id === "hub", "root_id should be 'hub' after trim and lowercase");

// Test 3: "home" maps to "system"
payload = buildAtlasPayload("home", "some_token", 6, 200000, "");
assert(payload.root_id === "system", "root_id should map 'home' to 'system'");
assert(payload.root_token === null, "explicit ID should override token");

// Test 4: raw path with token (picker)
payload = buildAtlasPayload("/path/to/my/folder", "abc-123-token", 6, 200000, "");
assert(payload.root_id === null, "root_id should be null for raw paths");
assert(payload.root_token === "abc-123-token", "root_token should be preserved for raw paths");

// Test 5: raw path without token (manual typing unsupported)
payload = buildAtlasPayload("/path/to/my/folder", null, 6, 200000, "");
assert(payload.root_id === null, "root_id should be null for raw paths without token");
assert(payload.root_token === null, "root_token should be null for raw paths without token");

// Test 6: limit and depth parses correctly
payload = buildAtlasPayload("hub", null, "10", "50000", "glob1, glob2");
assert(payload.max_depth === 10, "max_depth parsed correctly");
assert(payload.max_entries === 50000, "max_entries parsed correctly");
assert(payload.exclude_globs.length === 2, "exclude_globs parsed correctly");
assert(payload.exclude_globs[0] === "glob1" && payload.exclude_globs[1] === "glob2", "exclude_globs trimmed correctly");

if (failed > 0) {
    console.error(`\n${failed} tests failed!`);
    process.exit(1);
} else {
    console.log(`\nAll tests passed successfully!`);
}
