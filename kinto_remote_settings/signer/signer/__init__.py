from kinto import logger


def heartbeat(request):
    """Test that signer is operationnal.

    :param request: current request object
    :type request: :class:`~pyramid:pyramid.request.Request`
    :returns: ``True`` is everything is ok, ``False`` otherwise.
    :rtype: bool
    """
    for signer in request.registry.signers.values():
        try:
            signer.sign("This is a heartbeat test.")
        except Exception as e:
            logger.exception(e)
            return False
    return True
