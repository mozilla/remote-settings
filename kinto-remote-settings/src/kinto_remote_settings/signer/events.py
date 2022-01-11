class BaseEvent(object):
    def __init__(self, request, payload, impacted_objects, resource, original_event):
        self.request = request
        self.payload = payload
        self.impacted_objects = impacted_objects
        self.resource = resource
        self.original_event = original_event

    @property
    def impacted_records(self):
        return self.impacted_objects


class ReviewRequested(BaseEvent):
    def __init__(self, changes_count, comment, **kwargs):
        super().__init__(**kwargs)
        self.comment = comment
        self.changes_count = changes_count
        self.payload["comment"] = comment
        self.payload["changes_count"] = changes_count


class ReviewRejected(BaseEvent):
    def __init__(self, comment, **kwargs):
        super().__init__(**kwargs)
        self.comment = comment
        self.payload["comment"] = comment


class ReviewApproved(BaseEvent):
    def __init__(self, changes_count, **kwargs):
        super().__init__(**kwargs)
        self.changes_count = changes_count
        self.payload["changes_count"] = changes_count


class ReviewCanceled(BaseEvent):
    def __init__(self, changes_count, **kwargs):
        super().__init__(**kwargs)
        self.changes_count = changes_count
        self.payload["changes_count"] = changes_count
