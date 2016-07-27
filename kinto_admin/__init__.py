import pkg_resources
from pyramid.static import static_view

#: Module version, as defined in PEP-0396.
__version__ = pkg_resources.get_distribution("kinto-dist").version


def includeme(config):
    # Process settings to remove storage wording.

    # Expose capability.
    config.add_api_capability("admin",
                              version=__version__,
                              description="Serve the admin console.",
                              url="https://github.com/Kinto/kinto-admin/")

    static = static_view('kinto_admin:static', use_subpath=True)
    config.add_route('catchall_static', '/admin/*subpath')
    config.add_view(static, route_name="catchall_static")
