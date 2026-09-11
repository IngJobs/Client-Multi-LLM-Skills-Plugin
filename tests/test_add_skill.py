import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from add_skill import add_skill
from generate_manifests import generate


class AddSkillTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copy(ROOT / 'marketplace-metadata.json', self.root)

    def add(self, plugin='android-example', skill='example', platform='android'):
        return add_skill(self.root, platform, plugin, skill, '사용 시점: "예시"를 요청할 때\n설명')

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_new_plugin_creates_every_manifest_and_catalog(self):
        path = self.add()
        self.assertTrue(path.exists())
        config = json.loads((path.parents[2] / 'plugin-config.json').read_text())
        self.assertEqual(config['name'], 'android-example')
        for relative, expected in generate(self.root).items():
            self.assertEqual((self.root / relative).read_text(), expected)
        catalog = json.loads((self.root / '.claude-plugin/marketplace.json').read_text())
        self.assertEqual(catalog['plugins'][0]['source'], './plugins/android/android-example')

    def test_existing_config_and_skill_are_preserved(self):
        first = self.add()
        config_path = first.parents[2] / 'plugin-config.json'
        config = json.loads(config_path.read_text())
        config['version'] = '2.3.4'
        config['codex']['interface'] = {'displayName': 'Custom'}
        config_path.write_text(json.dumps(config))
        before = config_path.read_bytes(), first.read_bytes()
        self.add(skill='second')
        self.assertEqual(before, (config_path.read_bytes(), first.read_bytes()))
        manifest = json.loads((first.parents[2] / '.codex-plugin/plugin.json').read_text())
        self.assertEqual(manifest['version'], '2.3.4')
        self.assertEqual(manifest['interface']['displayName'], 'Custom')

    def test_duplicate_skill_and_plugin_name_leave_files_unchanged(self):
        self.add()
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.add()
        self.assertEqual(before, self.snapshot())
        with self.assertRaisesRegex(ValueError, 'duplicate plugin name'):
            self.add(platform='ios')
        self.assertEqual(before, self.snapshot())

    def test_invalid_path_and_description_do_not_write(self):
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.add(skill='../escape')
        with self.assertRaises(ValueError):
            add_skill(self.root, 'android', 'sample', 'sample', ' ')
        self.assertEqual(before, self.snapshot())

    def test_existing_targets_are_preserved_and_disabled_outputs_removed(self):
        first = self.add()
        plugin = first.parents[2]
        config_path = plugin / 'plugin-config.json'
        config = json.loads(config_path.read_text())
        config['targets'] = ['claude']
        config_path.write_text(json.dumps(config))
        self.add(skill='second')
        self.assertTrue((plugin / '.claude-plugin/plugin.json').exists())
        self.assertFalse((plugin / '.codex-plugin/plugin.json').exists())
        self.assertFalse((plugin / 'gemini-extension.json').exists())
        self.assertEqual(json.loads(config_path.read_text())['targets'], ['claude'])

    def test_dependency_failure_rolls_back_new_skill(self):
        first = self.add()
        config_path = first.parents[2] / 'plugin-config.json'
        config = json.loads(config_path.read_text())
        config['dependencies'] = ['missing-plugin']
        config_path.write_text(json.dumps(config))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'missing dependency'):
            self.add(skill='second')
        self.assertEqual(before, self.snapshot())
        self.assertFalse((first.parents[1] / 'second').exists())

    def test_cli_uses_script_repository_not_working_directory(self):
        shutil.copytree(ROOT / 'scripts', self.root / 'scripts')
        result = subprocess.run([
            sys.executable, '-B', str(self.root / 'scripts/add_skill.py'),
            '--platform', 'ios', '--plugin', 'ios-example', '--skill', 'example',
            '--description', 'Example skill',
        ], cwd=self.root.parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / 'plugins/ios/ios-example/gemini-extension.json').exists())


if __name__ == '__main__':
    unittest.main()
