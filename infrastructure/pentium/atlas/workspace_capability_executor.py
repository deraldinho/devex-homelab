from __future__ import annotations


class WorkspaceCapabilityExecutor:
    def __init__(self, broker, *, searcher=None):
        self._broker = broker
        self._searcher = searcher

    def __call__(self, capability: str, arguments: dict[str, object], _plan, _action):
        args = dict(arguments)
        if capability == "workspace_status":
            return self._broker.status()
        if capability == "workspace_list":
            return self._broker.list(str(args["area"]))
        if capability == "workspace_read":
            return self._broker.read(str(args["area"]), str(args["path"]))
        if capability == "workspace_search":
            if self._searcher is None:
                return ()
            return self._searcher.retrieve(str(args["query"]), max_items=6, max_bytes=2048)
        if capability == "workspace_create_note":
            return self._broker.write("notes", str(args["path"]), str(args["content"]), reason="self_work")
        if capability == "workspace_write":
            return self._broker.write(str(args["area"]), str(args["path"]), str(args["content"]), reason="self_work")
        if capability == "workspace_append":
            return self._broker.append(str(args["area"]), str(args["path"]), str(args["content"]), reason="self_work")
        if capability == "workspace_mkdir":
            return self._broker.mkdir(str(args["area"]), str(args["path"]))
        if capability == "workspace_move":
            return self._broker.move(str(args["area"]), str(args["path"]), str(args["destination_area"]), str(args["destination_path"]))
        if capability == "workspace_archive":
            return self._broker.archive(str(args["area"]), str(args["path"]))
        if capability == "workspace_trash":
            return self._broker.trash(str(args["area"]), str(args["path"]), reason="self_work")
        if capability == "workspace_restore":
            return self._broker.restore(str(args["trash_id"]))
        if capability == "workspace_purge":
            raise PermissionError("purge_requires_human_owner_path")
        raise PermissionError("workspace_capability_forbidden")
