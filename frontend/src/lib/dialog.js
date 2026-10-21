// Modal details panel on the native <dialog> element: the browser handles
// focus containment, Escape, the inert background and top-layer stacking.

export class DetailsDialog {
  constructor(root) {
    this.root = root;
    this.dialog = null;
    this.returnFocus = null;
  }

  get isOpen() {
    return Boolean(this.dialog?.open);
  }

  /**
   * Open with `buildContent(close)` rendered inside. On close, focus goes to
   * `returnFocus()` (a lookup, since the card may have re-rendered the opener).
   */
  open({ label, buildContent, returnFocus }) {
    this.returnFocus = returnFocus || null;
    if (!this.dialog) {
      this.dialog = document.createElement("dialog");
      this.dialog.className = "details";
      this.dialog.addEventListener("close", () => this._restoreFocus());
      // A click on the backdrop lands on the <dialog> itself, outside its panel.
      this.dialog.addEventListener("click", (e) => {
        if (e.target === this.dialog) this.close();
      });
      this._addSwipeToClose();
      this.root.append(this.dialog);
    }
    this.dialog.setAttribute("aria-label", label);
    this.dialog.replaceChildren(buildContent(() => this.close()));
    if (!this.dialog.open) this.dialog.showModal();
  }

  /** Re-render the open dialog's content in place. The <dialog> itself never leaves the DOM while open. */
  update(buildContent) {
    if (!this.isOpen) return;
    const scroll = this.dialog.firstElementChild?.scrollTop ?? 0;
    const focused = this.root.activeElement?.dataset?.key;
    this.dialog.replaceChildren(buildContent(() => this.close()));
    if (this.dialog.firstElementChild) this.dialog.firstElementChild.scrollTop = scroll;
    // Keep keyboard focus inside the dialog across content updates.
    const target = (focused && this.dialog.querySelector(`[data-key="${CSS.escape(focused)}"]`)) || this.dialog.querySelector("[autofocus]");
    target?.focus();
  }

  close() {
    if (this.dialog?.open) this.dialog.close();
  }

  _restoreFocus() {
    const target = this.returnFocus?.();
    if (target?.isConnected && typeof target.focus === "function") target.focus();
  }

  _addSwipeToClose() {
    let startY = null;
    this.dialog.addEventListener("touchstart", (e) => (startY = e.touches[0].clientY), { passive: true });
    this.dialog.addEventListener(
      "touchend",
      (e) => {
        if (startY != null && e.changedTouches[0].clientY - startY > 80 && this.dialog.firstElementChild?.scrollTop === 0) {
          this.close();
        }
        startY = null;
      },
      { passive: true },
    );
  }
}
