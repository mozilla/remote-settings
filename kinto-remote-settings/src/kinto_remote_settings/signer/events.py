from typing import Any


class BaseEvent(object):
    def __init__(
        self,
        request: Any,
        payload: dict[str, Any],
        impacted_objects: list[dict[str, Any]],
        resource: dict[str, Any],
        original_event: Any,
    ) -> None:
        self.request = request
        self.payload = payload
        self.impacted_objects = impacted_objects
        self.resource = resource
        self.original_event = original_event

    @property
    def impacted_records(self) -> list[dict[str, Any]]:
        return self.impacted_objects


class ReviewRequested(BaseEvent):
    def __init__(
        self,
        changes_count: int | None,
        changes_size_bytes: int | None,
        comment: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.comment = comment
        self.changes_count = changes_count
        self.changes_size_bytes = changes_size_bytes
        self.payload["comment"] = comment
        self.payload["changes_count"] = changes_count
        self.payload["changes_size_bytes"] = changes_size_bytes


class ReviewRejected(BaseEvent):
    def __init__(self, comment: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.comment = comment
        self.payload["comment"] = comment


class ReviewApproved(BaseEvent):
    def __init__(
        self, changes_count: int, changes_size_bytes: int, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.changes_count = changes_count
        self.changes_size_bytes = changes_size_bytes
        self.payload["changes_count"] = changes_count
        self.payload["changes_size_bytes"] = changes_size_bytes


class ReviewCanceled(BaseEvent):
    def __init__(self, changes_count: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.changes_count = changes_count
        self.payload["changes_count"] = changes_count
