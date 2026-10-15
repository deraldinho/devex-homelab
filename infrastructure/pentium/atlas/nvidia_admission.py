"""NVIDIA admission for Atlas inference is explicitly entitlement-gated."""
from __future__ import annotations
from .free_model_selection import ModelOffer, select_free_models

def eligible_nvidia_offers(offers, *, task, authorized, credential_rotated=False):
    """The installed Hermes credential must be rotated after accidental disclosure.
    Catalog presence, free model names, and Hermes configuration are not proof of zero cost.
    """
    if credential_rotated is not True:
        return ()
    return tuple(offer for offer in select_free_models(
        offers, task=task, authorized=frozenset(authorized))
        if offer.provider=="nvidia")
