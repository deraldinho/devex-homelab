"""Adapter between measured model profiles and the free-only OpenCode fallback.
Profiles are trusted application telemetry, never values supplied by an agent.
"""
from atlas_model_ranker import rank_models

def make_free_ranker(profiles, *, task, input_tokens=1000, output_tokens=500):
    profile_list=tuple(profiles)
    def select(allowed):
        allowed_set=set(allowed)
        candidates=[p for p in profile_list if p.model in allowed_set]
        return tuple(p.model for p in rank_models(candidates,task=task,
            input_tokens=input_tokens,output_tokens=output_tokens))
    return select
