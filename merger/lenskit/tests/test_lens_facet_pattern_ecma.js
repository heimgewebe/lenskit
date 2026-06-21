"use strict";

// ECMAScript Unicode-regex parity gate for the Facet v1 path pattern.
//
// The JSON-Schema `pattern` is consumed by ECMAScript-based validators. The repo
// runs Ajv (scripts/jsonl-validate.sh); Ajv compiles `pattern` with the `u` flag
// by default (unicodeRegExp: true). This test compiles the *actual* schema
// pattern with `new RegExp(pattern, "u")` — matching that default — and asserts
// the agreed Facet v1 path policy. It does NOT execute Ajv and makes no claim
// that Ajv validated the schema; it only checks the same regex semantics.
//
// Under `u`, an astral scalar (e.g. an emoji) is one code point, so a simple
// `[\uD800-\uDFFF]` class accepts emoji yet still rejects unpaired surrogate code
// units. The test uses only Node built-ins (no npm, no Ajv) and never re-declares
// the regex — it reads it from the schema file. It is a real test_*.js, so the
// facet model itself classifies it as `test`.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const schemaPath = path.resolve(
  __dirname,
  "../contracts/lens-facet.v1.schema.json",
);
const schema = JSON.parse(fs.readFileSync(schemaPath, "utf8"));
const pattern = schema.definitions.item.properties.path.pattern;

const regex = new RegExp(pattern, "u");
assert.equal(regex.unicode, true);

const cc = (n) => String.fromCharCode(n); // a single UTF-16 code unit
const cpt = (n) => String.fromCodePoint(n); // a Unicode scalar
const ZWJ = cc(0x200d);
const HI = cc(0xd800); // lone high surrogate code unit
const LO = cc(0xdc00); // lone low surrogate code unit
const BSLASH = cc(0x5c); // backslash, built to avoid source escapes

const accepted = [
  ".github/workflows/ci.yml",
  "merger/lenskit/core/lenses.py",
  "a",
  "a.b",
  "a-b/c_d.schema.json",
  "docs/überblick.md", // BMP Latin-1
  "docs/évidence.md",
  "docs/分析.md", // CJK
  "docs/a" + cc(0x0301) + ".md", // combining acute accent
  "docs/🔍.md", // emoji literal (valid surrogate pair)
  cpt(0x1f50d) + ".md", // same emoji via code point
  "docs/" + cc(0xd83d) + cc(0xdd0d) + ".md", // explicit valid UTF-16 pair
  "docs/" + cpt(0x1f468) + ZWJ + cpt(0x1f469) + ZWJ + cpt(0x1f467) + ".md", // ZWJ family
];

const rejected = [
  // C0 controls + DEL
  "a" + cc(0x00) + "b",
  "a" + cc(0x09) + "b",
  "a" + cc(0x0a) + "b",
  "a" + cc(0x0d) + "b",
  "a" + cc(0x1f) + "b",
  "a" + cc(0x7f) + "b",
  // C1 controls (including NEL U+0085)
  "a" + cc(0x80) + "b",
  "a" + cc(0x85) + "b",
  "a" + cc(0x9f) + "b",
  // line/paragraph separators and BOM
  "a" + cc(0x2028) + "b",
  "a" + cc(0x2029) + "b",
  "a" + cc(0xfeff) + "b",
  cc(0xfeff),
  // unpaired UTF-16 surrogate code units
  "x_" + HI + "_y.txt", // high then non-low
  "x_" + cc(0xdcff) + "_y.txt", // lone low
  "x_" + cc(0xdfff) + "_y.txt", // lone low
  LO + "_at_start.txt", // low at string start
  "high_at_end_" + HI, // high at string end
  "x_" + HI + "a" + LO + "_y.txt", // high and low both unpaired
  // whitespace-only
  "   ",
  cc(0xa0), // NBSP only
  cc(0x3000), // ideographic space only
  // existing grammar
  "",
  ".",
  "./a",
  "a//b",
  "a/./b",
  "a/",
  "/abs",
  "../x",
  "a/../b",
  "a" + BSLASH + "b",
  "C:/foo",
  "c:/foo",
];

for (const value of accepted) {
  assert.equal(
    regex.test(value),
    true,
    `expected ECMAScript pattern to accept ${JSON.stringify(value)}`,
  );
}
for (const value of rejected) {
  assert.equal(
    regex.test(value),
    false,
    `expected ECMAScript pattern to reject ${JSON.stringify(value)}`,
  );
}

console.log("lens-facet path pattern: ECMAScript Unicode parity OK");
