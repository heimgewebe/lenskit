"use strict";

// ECMAScript parity gate for the Facet v1 path pattern.
//
// The JSON-Schema `pattern` is consumed by ECMAScript-based validators (the repo
// already runs Ajv in scripts/jsonl-validate.sh). ECMAScript strings are UTF-16,
// so an astral character such as an emoji is a *surrogate pair* of code units.
// A naive `[\uD800-\uDFFF]` class would therefore reject valid emoji in a JS
// validator while Python's `re` (which sees code points) accepts them. This test
// loads the real pattern from the contract and asserts the ECMAScript semantics:
// valid surrogate pairs are accepted; unpaired surrogate code units and ASCII
// control characters are rejected. It uses only Node built-ins (no npm, no Ajv)
// and never re-declares the regex — it must read it from the schema file.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const schemaPath = path.resolve(
  __dirname,
  "../contracts/lens-facet.v1.schema.json",
);
const schema = JSON.parse(fs.readFileSync(schemaPath, "utf8"));
const pattern = schema.definitions.item.properties.path.pattern;
const regex = new RegExp(pattern);

const HI = String.fromCharCode(0xd800); // lone high surrogate code unit
const LO = String.fromCharCode(0xdc00); // lone low surrogate code unit

const accepted = [
  ".github/workflows/ci.yml",
  "merger/lenskit/core/lenses.py",
  "a",
  "a.b",
  "a-b/c_d.schema.json",
  "docs/überblick.md",
  "docs/évidence.md",
  "docs/分析.md",
  "docs/🔍.md", // literal emoji (valid UTF-16 surrogate pair)
  String.fromCodePoint(0x1f50d) + ".md", // same emoji via code point
  "docs/" + String.fromCharCode(0xd83d, 0xdd0d) + ".md", // explicit valid pair
];

const rejected = [
  // ASCII control characters
  "a" + String.fromCharCode(0x00) + "b",
  "a" + String.fromCharCode(0x09) + "b",
  "a" + String.fromCharCode(0x0a) + "b",
  "a" + String.fromCharCode(0x0d) + "b",
  "a" + String.fromCharCode(0x1f) + "b",
  "a" + String.fromCharCode(0x7f) + "b",
  "a" + String.fromCharCode(0x0a), // trailing newline
  // unpaired UTF-16 surrogate code units
  "x_" + HI + "_y.txt", // high followed by non-low
  "x_" + String.fromCharCode(0xdcff) + "_y.txt", // lone low
  "x_" + String.fromCharCode(0xdfff) + "_y.txt", // lone low
  LO + "_at_start.txt", // low at string start
  "high_at_end_" + HI, // high at string end
  "x_" + HI + "a" + LO + "_y.txt", // high and low both unpaired
  // existing grammar
  "",
  "   ",
  ".",
  "./a",
  "a//b",
  "a/./b",
  "a/",
  "/abs",
  "../x",
  "a/../b",
  "a\\b",
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

console.log("lens-facet path pattern: ECMAScript parity OK");
