"""Self-contained HTML dashboard generation (offline, no CDN).

``render_dashboard(state, live)`` renders the whole-system state into one inline
HTML file. With ``live=True`` (the web server) the page subscribes to ``/events``
for real-time host metrics; with ``live=False`` (a one-shot ``scan``) it's a
static snapshot.
"""

from .dashboard import render_dashboard

__all__ = ["render_dashboard"]
