from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "instock" / "core" / "crawling" / "stock_concept_rank.py"
SPEC = importlib.util.spec_from_file_location("stock_concept_rank", MODULE_PATH)
concept_rank = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(concept_rank)


class FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def __init__(self, response: str):
        self.response = response
        self.urls: list[str] = []

    def get(self, url: str, timeout: int):
        self.urls.append(url)
        return FakeResponse(self.response)


def test_ths_rank_parses_and_normalizes_percentages() -> None:
    html = """
    <table><thead><tr><th>序号</th><th>概念</th><th>涨跌幅</th><th>换手率</th></tr></thead>
    <tbody><tr><td>1</td><td>人工智能</td><td>5.20%</td><td>8.10%</td></tr></tbody></table>
    """
    session = FakeSession(html)

    result = concept_rank.stock_concept_theme_rank_ths(session=session)

    assert result.loc[0, "概念"] == "人工智能"
    assert result.loc[0, "涨跌幅"] == 5.2
    assert result.loc[0, "换手率"] == 8.1
    assert result.loc[0, "数据源"] == "同花顺题材排行"
    assert "/field/199112/order/desc/page/1/" in session.urls[0]


def test_ths_rank_parses_embedded_live_ranking_json() -> None:
    html = '''<input id="gnSection" value='{
      "a": {"platecode": "885001", "platename": "低空经济", "199112": 3.2, "zjjlr": 2.1, "zfl": 50},
      "b": {"platecode": "885002", "platename": "人工智能", "199112": 4.8, "zjjlr": 3.2, "zfl": 80}
    }'>'''

    result = concept_rank.stock_concept_theme_rank_ths(session=FakeSession(html))

    assert result["题材"].tolist() == ["人工智能", "低空经济"]
    assert result["排名"].tolist() == [1, 2]
    assert result.loc[0, "主力净流入"] == 3.2


def test_ths_rank_rejects_invalid_page_count() -> None:
    try:
        concept_rank.stock_concept_theme_rank_ths(pages=0)
    except ValueError as error:
        assert "pages" in str(error)
    else:
        raise AssertionError("pages=0 应抛出 ValueError")


def test_eastmoney_source_is_explicit(monkeypatch) -> None:
    class FakeAkshare:
        @staticmethod
        def stock_board_concept_name_em() -> pd.DataFrame:
            return pd.DataFrame({"板块名称": ["人工智能"]})

    import sys

    monkeypatch.setitem(sys.modules, "akshare", FakeAkshare)
    result = concept_rank.stock_concept_theme_rank(source="eastmoney")

    assert result.loc[0, "数据源"] == "东方财富概念排行（AkShare）"
