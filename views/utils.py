def center_on_parent(window, parent):
    """Center `window` on top of `parent` (or the screen if parent is None)."""
    window.update_idletasks()

    w = window.winfo_width()
    h = window.winfo_height()
    if w <= 1 or h <= 1:
        w = window.winfo_reqwidth()
        h = window.winfo_reqheight()

    if parent is not None and parent.winfo_viewable():
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
    else:
        x = (window.winfo_screenwidth() - w) // 2
        y = (window.winfo_screenheight() - h) // 2

    # Keep on-screen
    x = max(0, x)
    y = max(0, y)
    window.geometry(f"{w}x{h}+{x}+{y}")