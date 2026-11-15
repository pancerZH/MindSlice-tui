import string
import unittest

from mindslice_tui import i18n


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


class I18nTest(unittest.TestCase):
    def tearDown(self) -> None:
        i18n.use("en")

    def test_every_string_exists_in_every_language(self) -> None:
        for key, texts in i18n.STRINGS.items():
            self.assertEqual(len(texts), len(i18n.LANGUAGES), key)
            self.assertTrue(all(texts), key)
            self.assertEqual(len({frozenset(placeholders(text)) for text in texts}), 1, key)

    def test_switch_cycles_through_the_languages(self) -> None:
        self.assertEqual(i18n.t("search"), "Search")
        i18n.switch()
        self.assertEqual(i18n.t("search"), "搜索")
        self.assertEqual(i18n.t("card_count", count=3), "3 张卡片")
        i18n.switch()
        self.assertEqual(i18n.t("search"), "Search")


if __name__ == "__main__":
    unittest.main()
