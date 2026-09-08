"""Jev transport: images need the danger-zone header and probabilities arrive rounded to two decimals."""

import json
import math
import uuid

from ..provider import InvalidDecision, InvalidResponse
from . import CompatibleClient

PNG_PREFIX = "data:image/png;base64,"
IMAGE_HEADER = {"TypeSafe-Danger-Zone-Images": "true"}


def request_body(model, conversation, questions):
    assets, state = {}, []
    for message in conversation:
        blocks = []
        for block in message["content"]:
            if block["type"] == "text":
                blocks.append({"text": block["text"]})
                continue
            ref = str(uuid.uuid4())
            data = block["image_url"]["url"].removeprefix(PNG_PREFIX)
            assets[ref] = {"type": "image", "format": "png", "data_base64": data}
            blocks.append({"screenshot": ref})
        state.append({"role": message["role"], "content": blocks})
    return {
        "model": model,
        "state": {"conversation": state},
        "assets": assets,
        "questions": questions,
    }


def unit(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def parse_answers(data, groups, boxes=()):
    try:
        answers = {}
        for name, buttons in groups.items():
            answer = data["answers"][name]
            probabilities = answer["probabilities"]
            values = list(probabilities.values())
            if (
                answer["type"] != "choice"
                or answer["choice"] not in buttons
                or set(probabilities) != set(buttons)
                or not all(unit(v) for v in values)
                or abs(sum(values) - 1) > 0.0051 * len(values) + 0.001
                or not unit(answer["confidence"])
                or probabilities[answer["choice"]] < max(values) - 0.000001
            ):
                raise ValueError()
            answers[name] = {
                "choice": answer["choice"],
                "probabilities": probabilities,
                "confidence": answer["confidence"],
            }
        for name in boxes:
            answer = data["answers"][name]
            box = answer["box"]
            confidence = answer.get("confidence")
            if (
                answer["type"] != "box"
                or set(box) != {"top", "bottom", "left", "right"}
                or not all(unit(v) for v in box.values())
                or box["left"] > box["right"]
                or box["top"] > box["bottom"]
                or (confidence is not None and not unit(confidence))
            ):
                raise ValueError()
            answers[name] = {"box": dict(box), "confidence": confidence}
        usage = data["usage"]
        if any(
            type(usage[k]) is not int or usage[k] < 0 for k in ("input_tokens", "output_tokens")
        ):
            raise ValueError()
        model = data["model"]
        if not isinstance(model, str) or not model:
            raise ValueError()
        return (
            answers,
            {"input_tokens": usage["input_tokens"], "output_tokens": usage["output_tokens"]},
            model,
        )
    except (KeyError, TypeError, ValueError, AttributeError):
        raise InvalidDecision("Malformed Jev typed decision") from None


class TypesafeClient(CompatibleClient):
    def answer(self, conversation, questions, *, timeout=120, cancel=None):
        body = request_body(self.spec.model, conversation, questions)
        response = self.post(
            "/systemone", body, timeout=timeout, cancel=cancel, headers=IMAGE_HEADER
        )
        try:
            data = response.json()
        except ValueError:
            raise InvalidResponse("Malformed Jev response") from None
        groups = {
            name: set(question["criteria"])
            for name, question in questions.items()
            if question["type"] == "choice"
        }
        boxes = [name for name, question in questions.items() if question["type"] == "box"]
        try:
            return parse_answers(data, groups, boxes)
        except InvalidDecision as exc:
            raise InvalidDecision(str(exc), json.dumps(data)[:600]) from None
