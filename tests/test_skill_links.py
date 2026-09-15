from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent.parent


def document_links(text):
    """Read inline Markdown links, excluding fenced and inline code examples."""
    fence = None
    prose = []
    for line in text.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None:
            prose.append(line)
    text = re.sub(r"(`+).*?\1", "", "\n".join(prose))
    return re.findall(r"\[[^\]\n]*\]\(([^)\n]+)\)", text)


class SkillLinksTest(unittest.TestCase):
    def test_bundled_skill_links_resolve_from_referring_file(self):
        for source in (ROOT / "plugins").glob("*/*/skills/**/*.md"):
            for link in document_links(source.read_text(encoding="utf-8")):
                target = urlsplit(link)
                if target.scheme or target.netloc or not target.path:
                    continue
                with self.subTest(source=str(source.relative_to(ROOT)), link=link):
                    path = (source.parent / unquote(target.path)).resolve()
                    self.assertTrue(path.is_relative_to(ROOT / "plugins"))
                    self.assertTrue(path.is_file(), f"Missing resource: {path}")

    def test_code_examples_are_not_resource_links(self):
        text = (
            "[`SKILL.md`](../SKILL.md)\n"
            "`[example](url)`\n"
            "````markdown\n[template](placeholder.md)\n"
            "```json\n{}\n```\n````\n"
            "[review](../../review-pr/SKILL.md)\n"
        )
        self.assertEqual(document_links(text), ["../SKILL.md", "../../review-pr/SKILL.md"])


if __name__ == "__main__":
    unittest.main()
