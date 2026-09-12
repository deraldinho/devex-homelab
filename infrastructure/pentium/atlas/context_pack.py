from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextPack:
    sections: dict[str, str]
    estimated_tokens: int
    token_ceiling: int


class ContextPackBuilder:
    _CEILINGS = {"normal": 3000, "complex": 6000, "emergency": 8000}

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return (len(text.encode("utf-8")) + 3) // 4

    @staticmethod
    def _join(items) -> str:
        return "\n".join(str(item) for item in items if str(item))

    def build(self, *, mode: str, human: str = "", observation: str = "", observation_delta: str | None = None, memory=(), workspace=()) -> ContextPack:
        if mode not in self._CEILINGS:
            raise ValueError("context_mode_invalid")
        ceiling = self._CEILINGS[mode]
        max_chars = ceiling * 4
        ratios = {"human": 0.36, "observation": 0.25, "memory": 0.18, "workspace": 0.21}
        raw = {
            "human": str(human or ""),
            "observation": str(observation_delta if observation_delta is not None else observation or ""),
            "memory": self._join(memory),
            "workspace": self._join(workspace),
        }
        sections = {}
        remaining = max_chars
        for name in ("human", "observation", "memory", "workspace"):
            section_cap = int(max_chars * ratios[name])
            take = min(len(raw[name]), section_cap, remaining)
            sections[name] = raw[name][:take]
            remaining -= take
        combined = "\n".join(f"[{name}]\n{sections[name]}" for name in sections if sections[name])
        estimated = self._estimate_tokens(combined)
        while estimated > ceiling:
            reduced = False
            for name in ("workspace", "memory", "observation", "human"):
                if sections[name]:
                    trim = max(1, min(64, len(sections[name])))
                    sections[name] = sections[name][:-trim]
                    reduced = True
                    break
            if not reduced:
                break
            combined = "\n".join(f"[{name}]\n{sections[name]}" for name in sections if sections[name])
            estimated = self._estimate_tokens(combined)
        return ContextPack(sections=sections, estimated_tokens=estimated, token_ceiling=ceiling)
