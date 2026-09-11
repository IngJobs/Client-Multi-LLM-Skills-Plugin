import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from generate_manifests import CLI_FILES, dependency_order, generate, sync_outputs


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copy(ROOT / 'marketplace-metadata.json', self.root)

    def plugin(self, name, component='skills/demo/SKILL.md', **extra):
        path = self.root / 'plugins/shared' / name
        path.mkdir(parents=True)
        config = {'name': name, 'version': '0.1.0', 'description': name,
                  'author': {'name': 'Team'}, 'keywords': [], **extra}
        (path / 'plugin-config.json').write_text(json.dumps(config))
        (path / component).parent.mkdir(parents=True, exist_ok=True)
        (path / component).write_text('example')
        return path

    def test_agent_command_and_standalone_script_plugins(self):
        self.plugin('agent-only', component='agents/reviewer.md', targets=['claude'])
        self.plugin('command-only', component='commands/review.md', targets=['claude'])
        self.plugin('statusline', component='statusline.sh', resources=['statusline.sh'], targets=['claude'])
        outputs = generate(self.root)
        self.assertEqual(len(json.loads(outputs['.claude-plugin/marketplace.json'])['plugins']), 3)
        self.assertFalse(any(key.endswith('gemini-extension.json') for key in outputs))

    def test_missing_config_is_not_silently_skipped(self):
        self.plugin('valid')
        (self.root / 'plugins/shared/forgotten').mkdir()
        with self.assertRaisesRegex(ValueError, 'missing plugin-config'):
            generate(self.root)

    def test_disabled_targets_are_removed_and_check_does_not_write(self):
        path = self.plugin('sample')
        sync_outputs(self.root, generate(self.root))
        config = json.loads((path / 'plugin-config.json').read_text())
        config['targets'] = ['gemini']
        (path / 'plugin-config.json').write_text(json.dumps(config))
        outputs = generate(self.root)
        self.assertEqual(json.loads(outputs['.claude-plugin/marketplace.json'])['plugins'], [])
        stale = sync_outputs(self.root, outputs, check=True)
        self.assertIn('plugins/shared/sample/.codex-plugin/plugin.json', stale)
        self.assertTrue((path / '.codex-plugin/plugin.json').exists())
        sync_outputs(self.root, outputs)
        self.assertFalse((path / '.codex-plugin/plugin.json').exists())
        self.assertEqual(sync_outputs(self.root, outputs, check=True), [])

    def test_transitive_installation_order_and_native_claude_dependencies(self):
        self.plugin('base')
        self.plugin('middle', dependencies=['base'])
        self.plugin('top', dependencies=['middle'])
        outputs = generate(self.root)
        manifest = json.loads(outputs['plugins/shared/top/.claude-plugin/plugin.json'])
        self.assertEqual(manifest['dependencies'], ['middle'])
        self.assertNotIn('dependencies', json.loads(outputs['plugins/shared/top/.codex-plugin/plugin.json']))
        plugins = {
            path.parent.name: (str(path.parent), json.loads(path.read_text()))
            for path in self.root.glob('plugins/*/*/plugin-config.json')
        }
        self.assertEqual(dependency_order('top', 'codex', plugins), ['base', 'middle', 'top'])
        self.assertTrue(all(key.endswith('.json') for key in outputs))

    def test_missing_and_unsupported_dependencies(self):
        self.plugin('top', dependencies=['base'])
        with self.assertRaisesRegex(ValueError, 'missing dependency'):
            generate(self.root)
        self.plugin('base', targets=['claude'])
        with self.assertRaisesRegex(ValueError, 'does not target codex'):
            generate(self.root)

    def test_cycle_and_incomplete_per_cli_dependencies(self):
        self.plugin('first', dependencies=['second'])
        path = self.plugin('second', dependencies=['first'])
        with self.assertRaisesRegex(ValueError, 'cycle'):
            generate(self.root)
        config = json.loads((path / 'plugin-config.json').read_text())
        config['dependencies'] = {'claude': []}
        (path / 'plugin-config.json').write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, 'every selected target'):
            generate(self.root)

    def test_cli_specific_dependencies_are_explicit(self):
        self.plugin('base', targets=['claude'])
        self.plugin('top', dependencies={'claude': ['base'], 'codex': [], 'gemini': []})
        outputs = generate(self.root)
        self.assertEqual(
            json.loads(outputs['plugins/shared/top/.claude-plugin/plugin.json'])['dependencies'],
            ['base'],
        )
        self.assertNotIn('dependencies', json.loads(outputs['plugins/shared/top/.codex-plugin/plugin.json']))

    def test_missing_resource_and_legacy_dependencies_are_rejected(self):
        path = self.plugin('sample', resources=['missing.sh'])
        with self.assertRaisesRegex(ValueError, 'missing or invalid resource'):
            generate(self.root)
        config = json.loads((path / 'plugin-config.json').read_text())
        config.pop('resources')
        config['claude'] = {'dependencies': ['base']}
        (path / 'plugin-config.json').write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, 'move dependencies'):
            generate(self.root)


if __name__ == '__main__':
    unittest.main()
