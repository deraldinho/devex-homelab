from __future__ import annotations

import hashlib


class WorkspaceCapabilityExecutor:
    def __init__(self, broker, *, searcher=None, indexer=None, self_work=None):
        self._broker = broker
        self._searcher = searcher
        self._indexer = indexer
        self._self_work = self_work

    def _debit(self):
        if self._self_work is not None and self._self_work.current is not None:
            self._self_work.record_operation(now=self._self_work.current.updated_at)

    def _index_record(self, record):
        if self._indexer is None or record is None or not hasattr(record, "path"):
            return
        area, relative = str(record.path).split("/", 1)
        content = self._broker.read(area, relative)
        title = relative.rsplit("/", 1)[-1]
        digest = content[:512]
        self._indexer.upsert(str(record.path), title=title, digest=digest, content=content,
                             sha256=hashlib.sha256(content.encode("utf-8")).hexdigest())

    def __call__(self, capability: str, arguments: dict[str, object], _plan, _action):
        args = dict(arguments)
        if capability == "workspace_status": return self._broker.status()
        if capability == "workspace_list": return self._broker.list(str(args["area"]))
        if capability == "workspace_read": return self._broker.read(str(args["area"]), str(args["path"]))
        if capability == "workspace_search":
            return () if self._searcher is None else self._searcher.retrieve(str(args["query"]), max_items=6, max_bytes=2048)
        if capability == "workspace_purge": raise PermissionError("purge_requires_human_owner_path")
        self._debit()
        record = None
        if capability == "workspace_create_note": record = self._broker.write("notes", str(args["path"]), str(args["content"]), reason="self_work")
        elif capability == "workspace_write": record = self._broker.write(str(args["area"]), str(args["path"]), str(args["content"]), reason="self_work")
        elif capability == "workspace_append": record = self._broker.append(str(args["area"]), str(args["path"]), str(args["content"]), reason="self_work")
        elif capability == "workspace_mkdir": return self._broker.mkdir(str(args["area"]), str(args["path"]))
        elif capability == "workspace_move": record = self._broker.move(str(args["area"]), str(args["path"]), str(args["destination_area"]), str(args["destination_path"]))
        elif capability == "workspace_archive": record = self._broker.archive(str(args["area"]), str(args["path"]))
        elif capability == "workspace_trash":
            item = self._broker.trash(str(args["area"]), str(args["path"]), reason="self_work")
            if self._indexer is not None: self._indexer.remove(item.original_path)
            return item
        elif capability == "workspace_restore": record = self._broker.restore(str(args["trash_id"]))
        else: raise PermissionError("workspace_capability_forbidden")
        self._index_record(record)
        return record
