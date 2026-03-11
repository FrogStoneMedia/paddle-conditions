export function fireConfigChanged(editor, config) {
  editor.dispatchEvent(new CustomEvent("config-changed", {
    bubbles: true,
    composed: true,
    detail: { config },
  }));
}

export const EDITOR_STYLES = `
  .editor-row { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
  .editor-row label { min-width: 120px; font-weight: 500; }
  .editor-row input, .editor-row select { flex: 1; padding: 8px; border: 1px solid var(--divider-color, #e0e0e0); border-radius: 4px; }
  .editor-row ha-switch { flex: none; }
`;
