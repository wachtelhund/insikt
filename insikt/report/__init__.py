"""Self-contained HTML report generation (README §5, §9 v0 shortcut).

``render_report`` assembles every view's payload from :mod:`insikt.views` and the
hygiene result, then inlines it into a single offline HTML file — no CDN, no
network, Raspberry-Pi friendly.
"""

from .builder import render_report

__all__ = ["render_report"]
