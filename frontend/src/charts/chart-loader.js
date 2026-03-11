// Chart.js loader — tree-shaken imports, deferred registration
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  TimeScale,
  Filler,
  Legend,
  Tooltip,
} from "chart.js";

// Side-effect: registers custom date adapter
import "./date-adapter.js";

let registered = false;

export function ensureChartReady() {
  if (registered) return;
  Chart.register(
    LineController,
    LineElement,
    PointElement,
    LinearScale,
    TimeScale,
    Filler,
    Legend,
    Tooltip
  );
  registered = true;
}

export { Chart };
