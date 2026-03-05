/**
 * Utility for building the Atlas API payload.
 * Isolated here for safer testability without DOM dependencies.
 */

function buildAtlasPayload(rootPath, rootToken, depth, limit, excludes) {
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

// Export for Node.js test environment
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { buildAtlasPayload };
}
