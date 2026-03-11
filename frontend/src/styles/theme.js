// Shared CSS using HA theme variables for consistent styling
export const CARD_STYLES = `
  :host {
    --pc-go: #4CAF50;
    --pc-caution: #FF9800;
    --pc-nogo: #F44336;
    --pc-grey: #9E9E9E;
  }
  ha-card {
    padding: 16px;
    font-family: var(--ha-card-header-font-family, inherit);
    color: var(--primary-text-color, #212121);
    background: var(--ha-card-background, var(--card-background-color, white));
    border-radius: var(--ha-card-border-radius, 12px);
    box-shadow: var(--ha-card-box-shadow, none);
  }
  .card-header {
    font-size: 1.2em;
    font-weight: 500;
    padding-bottom: 8px;
    color: var(--ha-card-header-color, var(--primary-text-color));
  }
  .rating-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.8em;
    font-weight: 600;
    color: white;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .progress-bar {
    height: 6px;
    border-radius: 3px;
    background: var(--divider-color, #e0e0e0);
    overflow: hidden;
    flex: 1;
  }
  .progress-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.6s ease;
  }
  .icon-circle {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .icon-circle ha-icon {
    --mdc-icon-size: 20px;
    color: white;
  }
  .empty-state {
    text-align: center;
    padding: 24px;
    color: var(--secondary-text-color, #757575);
    font-style: italic;
  }
`;
