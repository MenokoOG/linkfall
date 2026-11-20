// Runs the Python suite on Pyodide with exactly what the site ships (ADR 0012, plan section 10).
//
// Run from the repo root, after the build and the test-wheel fetch:
//   python scripts/build_pages.py && python scripts/fetch_test_wheels.py
//   node scripts/test_pyodide.mjs [--dist dist] [--wheels .cache/pyodide-test-wheels] [-- pytest args]
//
// Pyodide, its packages, the pure wheels and the linkfall package all come from dist/runtime, the
// same files the page loads. The tests are read from this checkout. Left out, each for a reason a
// browser tab can't meet: test_api_misc.py imports uvicorn and serves on a real socket,
// test_supervisor_http_client.py runs a socket server on a thread, one replay test starts a
// subprocess, and test_web_static.py checks the server serving web/, which the hosted copy leaves to
// GitHub Pages (linkfall.zip has no web/).
import { readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const LEFT_OUT = [
  '--ignore=tests/test_api_misc.py',
  '--ignore=tests/test_supervisor_http_client.py',
  '--ignore=tests/test_web_static.py',
  '--deselect=tests/test_eventlog_consistency.py::test_replay_loads_no_agent_or_supervisor_code',
];

// Pyodide takes a plain Uint8Array, not Node's Buffer subclass.
function bytes(path) {
  const data = readFileSync(path);
  return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
}

function parseArgs(argv) {
  const options = { dist: 'dist', wheels: '.cache/pyodide-test-wheels', pytest: [] };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--') {
      options.pytest = argv.slice(i + 1);
      break;
    }
    if (argv[i] === '--dist') options.dist = argv[++i];
    else if (argv[i] === '--wheels') options.wheels = argv[++i];
    else throw new Error(`unknown argument: ${argv[i]}`);
  }
  return options;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const repo = resolve('.');
  const runtime = resolve(options.dist, 'runtime');
  const manifest = JSON.parse(readFileSync(join(runtime, 'manifest.json'), 'utf8'));
  const { loadPyodide } = await import(pathToFileURL(join(runtime, 'pyodide', 'pyodide.mjs')).href);
  const py = await loadPyodide({ indexURL: join(runtime, 'pyodide') + '/' });
  await py.loadPackage(manifest.packages, { messageCallback: () => {} });

  const site = py.runPython('import site; site.getsitepackages()[0]');
  const testWheels = readdirSync(options.wheels).filter((name) => name.endsWith('.whl'));
  for (const path of [...manifest.wheels.map((n) => join(runtime, n)), ...testWheels.map((n) => join(options.wheels, n))]) {
    py.unpackArchive(bytes(path), 'zip', { extractDir: site });
  }
  py.FS.mkdirTree('/app');
  py.unpackArchive(bytes(join(runtime, manifest.app)), 'zip', { extractDir: '/app' });
  py.FS.mkdirTree('/repo');
  py.FS.mount(py.FS.filesystems.NODEFS, { root: repo }, '/repo');

  py.globals.set('PYTEST_ARGS', py.toPy([
    '-p', 'no:cacheprovider', '-q', '-m', 'not integration', '-o', 'pythonpath=tests',
    ...LEFT_OUT, ...options.pytest, 'tests',
  ]));
  const code = await py.runPythonAsync(`
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, '/app')
os.chdir('/repo')
from linkfall.browser.bridge import install_thread_patches
install_thread_patches()  # what the page does at start-up
import linkfall, pydantic, fastapi
assert linkfall.__file__.startswith('/app/'), linkfall.__file__  # the shipped copy, not src/
print('python', sys.version.split()[0], 'pydantic', pydantic.__version__, 'fastapi', fastapi.__version__, 'linkfall from', os.path.dirname(linkfall.__file__))
import pytest
int(pytest.main(list(PYTEST_ARGS)))
`);
  return code;
}

main().then(
  (code) => process.exit(code),
  (error) => {
    console.error(error);
    process.exit(1);
  },
);
