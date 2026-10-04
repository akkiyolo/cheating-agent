import json
import random

import pytest

from app.services import question_bank as qb
from app.services.grading import grade_static, outputs_match, parse_number


@pytest.mark.parametrize("tid", sorted(qb.TEMPLATES))
def test_every_template_generates_valid_instance(tid: str) -> None:
    tpl = qb.TEMPLATES[tid]
    for seed in range(5):
        rng = random.Random(seed)
        inst = qb.finalize(tpl, tpl.gen(rng), rng, shuffle_options=True)
        assert inst["prompt"]
        key = inst["answer_key"]
        if "options" in inst:
            ids = {o["id"] for o in inst["options"]}
            texts = [o["text"] for o in inst["options"]]
            assert len(set(texts)) == len(texts), f"duplicate options in {tid}: {texts}"
            assert key["correct"] and set(key["correct"]) <= ids
            if not key["multi"]:
                assert len(key["correct"]) == 1
        elif inst["kind"] == "coding":
            assert len(key["tests"]) >= 5
            assert inst["coding"]["examples"] == key["tests"][: len(inst["coding"]["examples"])]
        json.dumps(inst)  # must be JSON-serialisable for storage


def test_default_composition_counts() -> None:
    qs = qb.generate_question_set(42)
    kinds = [q["kind"] for q in qs]
    assert len(qs) == 21
    assert sum(k in ("mcq", "true_false") for k in kinds) == 10
    assert kinds.count("numerical") == 3
    assert kinds.count("multi_select") == 2
    assert kinds.count("coding") == 2
    assert kinds.count("text") == 2
    assert kinds.count("image") == 1
    assert kinds.count("table") == 1


def test_sessions_are_randomised_and_seed_reproducible() -> None:
    a, b, a2 = qb.generate_question_set(1), qb.generate_question_set(2), qb.generate_question_set(1)
    assert [q["prompt"] for q in a] == [q["prompt"] for q in a2]
    assert [q["prompt"] for q in a] != [q["prompt"] for q in b]


def test_public_view_never_leaks_answers() -> None:
    qs = qb.generate_question_set(7)
    for i, q in enumerate(qs):
        view = qb.public_view(q, i, len(qs))
        blob = json.dumps(view)
        assert "answer_key" not in view
        assert "template" not in view
        if q["kind"] == "image":
            assert view["image"] == {"alt": "Question figure"}
        if q["kind"] == "coding":
            # only the visible examples are present, not the hidden tests
            hidden = q["answer_key"]["tests"][len(q["coding"]["examples"]):]
            assert all(t["input"] not in blob for t in hidden if len(t["input"]) > 40)


def test_grading_choice_numeric_text() -> None:
    qs = qb.generate_question_set(3)
    for q in qs:
        key = q["answer_key"]
        if key["type"] == "choice":
            good = {"option_ids": key["correct"]} if key["multi"] else {"option_id": key["correct"][0]}
            assert grade_static(q, good)[0]
            wrong = next(o["id"] for o in q["options"] if o["id"] not in key["correct"])
            bad = {"option_ids": [wrong]} if key["multi"] else {"option_id": wrong}
            assert not grade_static(q, bad)[0]
        elif key["type"] == "numeric":
            assert grade_static(q, {"value": str(key["value"])})[0]
            assert not grade_static(q, {"value": str(key["value"] + 1)})[0]
        elif key["type"] == "text":
            assert grade_static(q, {"value": "  " + key["accepted"][0].upper() + ". "})[0]
            assert not grade_static(q, {"value": "definitely wrong"})[0]
    assert grade_static(qs[0], None) == (False, 0.0)


def test_parse_number_and_output_match() -> None:
    assert parse_number("1,234.5") == 1234.5
    assert parse_number("−3.2") == -3.2
    assert parse_number("approx 0.25 units") == 0.25
    assert parse_number("abc") is None
    assert outputs_match("1\n2\n", "1  \n2")
    assert not outputs_match("1\n2\n", "1\n3\n")


def test_image_render_is_png() -> None:
    from app.services.images import render

    qs = qb.generate_question_set(11)
    img_q = next(q for q in qs if q["kind"] == "image")
    data = render(img_q["image"])
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
