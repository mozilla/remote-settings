import logging
from typing import Any


logger = logging.getLogger(__name__)


def heartbeat(request: Any) -> bool:
    """Test that signer is operational.

    :param request: current request object
    :type request: :class:`~pyramid:pyramid.request.Request`
    :returns: ``True`` is everything is ok, ``False`` otherwise.
    :rtype: bool
    """
    for signer in request.registry.signers.values():
        try:
            signer.sign("This is a heartbeat test.")

            # Additional checks for this signer backend.
            signer.healthcheck(request)
        except Exception as e:
            logger.exception(e)
            return False
    return True
