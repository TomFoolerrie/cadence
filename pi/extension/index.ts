/**
 * Pi package extension entry point.
 *
 * The root `package.json` `pi.extensions` lists `./pi/extension`; Pi resolves an
 * extension directory to its `index.ts` and imports the module's DEFAULT export,
 * which must be an `ExtensionFactory` ((pi) => void). See the loader contract in
 * `@earendil-works/pi-coding-agent` (`jiti.import(path, { default: true })` →
 * `factory(api)`).
 */

import { makeScopeGate } from "./scope-gate.ts";

export default makeScopeGate();
