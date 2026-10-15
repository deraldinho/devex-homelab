"""Per-job durable OpenCode session pool; no unpriced model access."""
import hashlib
import json
from pathlib import Path
from .opencode_http_transport import OpenCodeHTTPTransport

class OpenCodeSessionPool:
    def __init__(self, *, base_url, password, directory, journal_dir,
                 authorized_free_models, opener=None, timeout=15):
        self.base_url=base_url
        self.password=password
        self.directory=directory
        self.journal_dir=Path(journal_dir)
        self.authorized=frozenset(authorized_free_models)
        self.opener=opener
        self.timeout=timeout
    def __call__(self, *, model, prompt, context, max_tokens):
        if model not in self.authorized:
            raise ValueError("model lacks trusted zero-cost authorization")
        key=hashlib.sha256(json.dumps([model,prompt,context,max_tokens],
            ensure_ascii=False,sort_keys=True).encode("utf-8")).hexdigest()
        # Every distinct request owns a separate, persistent journal.
        transport=OpenCodeHTTPTransport(base_url=self.base_url,password=self.password,
            directory=self.directory,journal_path=self.journal_dir/(key+".json"),
            opener=self.opener,timeout=self.timeout)
        return transport(model=model,prompt=prompt,context=context,max_tokens=max_tokens)
