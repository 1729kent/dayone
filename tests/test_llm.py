import pytest
from pydantic import BaseModel

from dayone.common.llm import LLM, FakeLLM, LLMError


class Out(BaseModel):
    x: int


class Flaky:
    """genai client の代役。2回 429 相当で失敗して3回目に成功する"""

    def __init__(self):
        self.calls = 0
        outer = self

        class Models:
            def generate_content(self, **kw):
                outer.calls += 1
                if outer.calls < 3:
                    raise RuntimeError("429 RESOURCE_EXHAUSTED")

                class R:
                    text = '{"x": 7}'

                return R()

        self.models = Models()


class AlwaysFail:
    def __init__(self):
        class Models:
            def generate_content(self, **kw):
                raise RuntimeError("429 RESOURCE_EXHAUSTED")

        self.models = Models()


def test_gen_json_retries_then_parses():
    llm = LLM(model="m", client=Flaky())
    llm._sleep = lambda s: None
    out = llm.gen_json("p", Out)
    assert out.x == 7


def test_gen_json_raises_after_3():
    llm = LLM(model="m", client=AlwaysFail())
    llm._sleep = lambda s: None
    with pytest.raises(LLMError):
        llm.gen_json("p", Out)


def test_fake_llm():
    f = FakeLLM(json_responses=[Out(x=1)], text_responses=["hi"])
    assert f.gen_json("p", Out).x == 1
    assert f.gen_text("p") == "hi"
