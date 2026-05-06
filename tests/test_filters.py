from dataclasses import dataclass

from app.pipeline.filters import contains_excluded_keyword, filter_excluded_items, load_exclude_keywords


@dataclass
class Item:
    text: str


def test_load_exclude_keywords_deduplicates_and_ignores_comments(tmp_path) -> None:
    path = tmp_path / "exclude.txt"
    path.write_text("реклама\n# comment\nРеклама\nпромокод # inline\n", encoding="utf-8")

    assert load_exclude_keywords(str(path)) == ["реклама", "промокод"]


def test_contains_excluded_keyword_is_case_insensitive() -> None:
    assert contains_excluded_keyword("Это РЕКЛАМА", ["реклама"]) is True


def test_filter_excluded_items() -> None:
    items = [Item(text="good news"), Item(text="bad promo")]

    filtered_items = filter_excluded_items(items, ["promo"])

    assert [item.text for item in filtered_items] == ["good news"]
