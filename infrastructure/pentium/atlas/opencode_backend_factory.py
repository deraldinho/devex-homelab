"""Opt-in composition of trusted zero-cost OpenCode backend for Atlas."""
from .free_model_selection import select_free_models
from .governed_inference_router import GovernedInferenceRouter
from .opencode_inference_adapter import OpenCodeInferenceAdapter
from .opencode_session_pool import OpenCodeSessionPool

def make_opencode_backend_factory(*, offers, authorized, base_url, password,
                                  directory, journal_dir, telemetry=None,
                                  adaptive_health=None, opener=None, timeout=15):
    """Returns a build_owner-compatible factory; never changes Hermes by default."""
    offers=tuple(offers)
    authorized=frozenset(authorized)
    valid={
        ("opencode",offer.model)
        for offer in offers
        if offer.provider=="opencode" and
        ("opencode",offer.model) in authorized and
        offer.zero_cost_verified is True and
        offer.input_price_per_million==0 and
        offer.output_price_per_million==0 and
        bool(offer.tasks)
    }
    if not valid:raise ValueError("no trusted zero-cost OpenCode offers")
    ids=frozenset(model for _,model in valid)
    pool=OpenCodeSessionPool(base_url=base_url,password=password,directory=directory,
        journal_dir=journal_dir,authorized_free_models=ids,opener=opener,timeout=timeout)
    backends={
        identity:OpenCodeInferenceAdapter(model=identity[1],transport=pool,
                                        authorized_models=ids)
        for identity in valid
    }
    def factory(_hermes_config):
        return GovernedInferenceRouter(offers=offers,authorized=valid,backends=backends,
                                       telemetry=telemetry,adaptive_health=adaptive_health)
    return factory
