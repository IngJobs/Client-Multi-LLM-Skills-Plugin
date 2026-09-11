import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('generator', ROOT / 'scripts/generate_manifests.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class ManifestSettingsTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'plugins/android/android-code-quality/plugin-config.json').read_text())

    def render(self):
        return {path: json.loads(text) for path, text in generator.render(self.config).items()}

    def test_nested_overrides_keep_common_defaults_and_replace_arrays(self):
        self.config['codex']['author'] = {'url': 'https://example.com'}
        self.config['codex']['keywords'] = ['custom']
        result = self.render()['.codex-plugin/plugin.json']
        self.assertEqual(result['author']['name'], self.config['author']['name'])
        self.assertEqual(result['author']['url'], 'https://example.com')
        self.assertEqual(result['keywords'], ['custom'])

    def test_common_metadata_and_optional_interface(self):
        result = self.render()
        for path in ['.claude-plugin/plugin.json', '.codex-plugin/plugin.json']:
            for field in ['description', 'author', 'keywords']:
                self.assertEqual(result[path][field], self.config[field])
        self.assertNotIn('$schema', result['.codex-plugin/plugin.json'])
        self.assertNotIn('interface', result['.codex-plugin/plugin.json'])
        self.config['codex']['interface'] = {'displayName': 'Optional UI'}
        self.assertEqual(self.render()['.codex-plugin/plugin.json']['interface']['displayName'], 'Optional UI')

    def test_settings_do_not_leak_between_clis(self):
        before = json.loads(json.dumps(self.config))
        self.config['claude'] = {'skills': ['./skills/'], 'author': {'url': 'https://example.com'}}
        self.config['gemini'] = {'contextFileName': 'AGENTS.md'}
        result = self.render()
        self.assertEqual(result['.claude-plugin/plugin.json']['author']['name'], self.config['author']['name'])
        self.assertEqual(result['.claude-plugin/plugin.json']['skills'], ['./skills/'])
        self.assertEqual(result['.codex-plugin/plugin.json']['skills'], './skills/')
        self.assertEqual(result['gemini-extension.json']['contextFileName'], 'AGENTS.md')
        self.assertNotIn('contextFileName', result['.codex-plugin/plugin.json'])
        self.assertEqual(self.config['codex'], before['codex'])

    def test_null_removes_optional_fields(self):
        self.config['codex']['keywords'] = None
        self.config['claude']['author'] = None
        result = self.render()
        self.assertNotIn('keywords', result['.codex-plugin/plugin.json'])
        self.assertNotIn('author', result['.claude-plugin/plugin.json'])

    def test_identity_is_shared_and_not_overridable(self):
        for manifest in self.render().values():
            self.assertEqual(manifest['name'], self.config['name'])
            self.assertEqual(manifest['version'], self.config['version'])
        for cli in generator.CLI_FILES:
            for field in ['name', 'version']:
                with self.subTest(cli=cli, field=field):
                    self.config[cli][field] = None
                    with self.assertRaises(ValueError):
                        self.render()
                    del self.config[cli][field]

    def test_sections_must_be_objects_and_typos_are_rejected(self):
        self.config['gemini'] = []
        with self.assertRaises(ValueError):
            self.render()
        self.config['gemini'] = {}
        self.config['codxe'] = {}
        with self.assertRaises(ValueError):
            self.render()


if __name__ == '__main__':
    unittest.main()
